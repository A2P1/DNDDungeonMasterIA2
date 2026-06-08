import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from typing import Callable, Literal, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from tools.entidades import dañar_enemigo, dañar_npc, get_info_entidad, get_estado_combate
from tools.dados import tirar_d20, tirar_dado
from tools.inventario import get_armas, verificar_arma_en_accion, usar_item
from tools.campana import get_siguiente_beat # Para inyectar el beat actual como contexto narrativo del combate
from agentes.secretario import cargar_diario, guardar_diario, aplicar_delta, DeltaDiario # Para registrar el desenlace de cada combate en el diario
from config import STATS_PATH, COMBATE_PROMPT_PATH, ENTIDADES_PATH, MODEL_NAME

load_dotenv()

with open(COMBATE_PROMPT_PATH, 'r', encoding='utf-8') as f:
    prompt = f.read().strip()


class EvaluacionAccion(BaseModel):
    viable: bool
    razon: Optional[str] = None
    tipo: Optional[Literal["ataque", "accion"]] = None
    atributo: Optional[Literal["fue", "des", "con", "int", "sab", "car"]] = None
    dc: Optional[int] = Field(default=None, ge=8, le=20)
    dado_daño: Optional[str] = None
    objetivo: Optional[str] = None
    efecto_exito: Optional[str] = None
    efecto_fallo: Optional[str] = None
    termina_combate: bool = False
    motivo_fin: Optional[str] = None
    usa_item: Optional[str] = None


llm = ChatOpenAI(model=MODEL_NAME, temperature=0.9)
llm_evaluar = ChatOpenAI(model=MODEL_NAME, temperature=0.3).with_structured_output(EvaluacionAccion)


def _get_tipo_entidad(entidad_id: str) -> str:
    if not ENTIDADES_PATH.exists():
        return "enemigo"
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
        entidades = json.load(f)
    for e in entidades.get("enemigos", []):
        if e.get("id") == entidad_id:
            return "enemigo"
    for n in entidades.get("npcs", []):
        if n.get("id") == entidad_id:
            return "npc"
    return "enemigo"


def _cargar_jugador() -> dict:
    if not STATS_PATH.exists():
        return {}
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _guardar_jugador(jugador: dict):
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(jugador, f, indent=2, ensure_ascii=False)


def _contexto_escena_msgs() -> list: # Beat + diario + entidades vivas del beat como SystemMessages: el LLM de combate no debe inventar lugar, NPCs ni armas
    msg = []
    siguiente_beat = get_siguiente_beat.invoke({})

    if siguiente_beat == "CAMPAÑA COMPLETA":
        msg.append(SystemMessage(content=f"La campaña está completa."))
        return msg
    beat_id = json.loads(siguiente_beat).get("siguiente_beat", {}).get("id")
    diario = cargar_diario()
    msg.append(SystemMessage(content=f"Diario de los hechos importantes del jugador hasta ahora:\n{json.dumps(diario.model_dump(), ensure_ascii=False)}"))
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
        entidades = json.load(f)
    for e in entidades.get("enemigos", []):
        if e.get("beat_origen") == beat_id and e.get("estado") == "vivo":
            msg.append(SystemMessage(content=f"Enemigo presente en el combate: {e['nombre']}. Descripción: {e.get('descripcion', '')}. Arma: {e.get('arma', 'desconocida')}."))
    for n in entidades.get("npcs", []):
        if n.get("beat_origen") == beat_id and n.get("estado") == "vivo":
            msg.append(SystemMessage(content=f"NPC presente en el combate: {n['nombre']}. Descripción: {n.get('descripcion', '')}. Arma: {n.get('arma', 'desconocida')}."))
    return msg



def _narrar(contexto: str) -> str:
    msgs = [
        SystemMessage(content=prompt + "\n\nMODO: NARRAR"),
        *_contexto_escena_msgs(), # Inyectamos beat + diario para que el combate no invente ubicación ni mezcle el nombre del jugador con NPCs
        HumanMessage(content=contexto)
    ]
    return llm.invoke(msgs).content


def _evaluar_accion(accion: str, contexto_combate: str) -> dict:
    try:
        evaluacion = llm_evaluar.invoke([
            SystemMessage(content=prompt + "\n\nMODO: EVALUAR ACCIÓN"),
            HumanMessage(content=f"Contexto del combate:\n{contexto_combate}\n\nAcción del jugador: {accion}")
        ])
        return evaluacion.model_dump(exclude_none=True)
    except Exception:
        return {"viable": False, "razon": "No se pudo interpretar la acción"}


def _respuesta_turno(jugador: dict, estado: dict, narracion: str, resultado, tirada: int) -> dict:
    if resultado in ("victoria", "derrota", "resolucion"): # Al cerrar combate, registramos el hecho en el diario para que el narrador se entere en el siguiente turno
        prefijo = {"victoria": "Combate ganado", "derrota": "Jugador derrotado en combate", "resolucion": "Combate resuelto sin matar a todos"}[resultado]
        primera_frase = narracion.split('.')[0][:200] # Primera frase de la narración para dar sabor sin inflar el diario
        diario = cargar_diario()
        guardar_diario(aplicar_delta(diario, DeltaDiario(hechos=[f"{prefijo}: {primera_frase}"])))
    return {
        "narracion": narracion,
        "jugador_vida": jugador["vida_actual"],
        "jugador_vida_max": jugador["vida_max"],
        "entidades_vivas": estado.get("enemigos_vivos", []),
        "combate_terminado": estado.get("combate_terminado", False),
        "resultado": resultado,
        "tirada": tirada
    }


def procesar_turno(beat_id: str, accion: str) -> dict:
    jugador = _cargar_jugador()
    estado_combate = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    entidades_vivas = estado_combate.get("enemigos_vivos", [])
    narracion = [] 

    if not entidades_vivas:
        return _respuesta_turno(jugador, estado_combate, "No hay enemigos vivos. El combate ha terminado.", "victoria", None)
    
    armas_disponibles = get_armas(jugador)
    accion_con_arma = verificar_arma_en_accion(accion, armas_disponibles)
    if accion_con_arma["estado"] == "no_en_inventario":
        narracion.append(f"Mencionas usar '{accion_con_arma['nombre']}', pero no lo tienes en tu inventario. No puedes usarlo.")
    elif accion_con_arma["estado"] == "encontrada":
        jugador["arma"] = accion_con_arma["arma"] 
        _guardar_jugador(jugador)
    arma_actual = jugador.get("arma", {})
    consumibles = [item for item in jugador.get("inventario", []) if item.get("tipo") == "consumible"]
    enemigos_vivos = entidades_vivas
    contexto = (
        f"Jugador: {jugador['nombre']} ({jugador.get('clase', '?')}), "
        f"Arma: {arma_actual.get('nombre', 'sus puños')} (dado: {arma_actual.get('dado_daño', '1d6')}), "
        f"Atributos: {json.dumps(jugador.get('atributos', {}))}\n"
        f"Consumibles disponibles: {json.dumps(consumibles, ensure_ascii=False)}\n"
        f"Enemigos vivos: {json.dumps(enemigos_vivos, ensure_ascii=False)}"
    )
    evaluacion = _evaluar_accion(accion, contexto)

    if not evaluacion.get("viable", False):
        narracion.append(_narrar(f"La acción no es viable: {evaluacion.get('razon', 'sin razón específica')}. Intenta otra cosa."))
        return _respuesta_turno(jugador, estado_combate, "\n\n".join(narracion), None, None)
    objetivo_id = evaluacion.get("objetivo") or entidades_vivas[0]["id"]
    enemigo_objetivo = json.loads(get_info_entidad.invoke({"entidad_id": objetivo_id}))
    Armadura = enemigo_objetivo.get("ac", 10)
    
    # TURNO JUGADOR:

    tirada = tirar_d20.invoke({})
    if tirada + jugador.get("atributos", {}).get(evaluacion.get("atributo", ""), 0) >= Armadura:
        daño = tirar_dado.invoke({ "dado": evaluacion.get("dado_daño", "1d6") })

        entidad = _get_tipo_entidad(objetivo_id)
        if entidad == "enemigo":
            resultado_daño = json.loads(dañar_enemigo.invoke({"enemigo_id": objetivo_id, "daño": daño}))
            narracion.append(resultado_daño["mensaje"])
        elif entidad == "npc":
            resultado_daño = json.loads(dañar_npc.invoke({"npc_id": objetivo_id, "daño": daño}))
            narracion.append(resultado_daño["mensaje"])
    else:
        narracion.append(_narrar(f"Fallas el ataque contra {enemigo_objetivo['nombre']}."))
    estado_combate = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    entidades_vivas = estado_combate.get("enemigos_vivos", [])
    if not entidades_vivas:
        return _respuesta_turno(jugador, estado_combate, "No hay enemigos vivos. El combate ha terminado.", "victoria", tirada)
    
    # TURNO ENEMIGOS
    #Por cada enemigo vivo (máximo 2)
    for enemigo in entidades_vivas[:2]:
        tirada_enemigo = tirar_d20.invoke({})
        info_enemigo = json.loads(get_info_entidad.invoke({"entidad_id": enemigo["id"]}))
        if tirada_enemigo + info_enemigo.get("atributos", {}).get("fue", 0) >= jugador.get("ac", 10):
            daño_enemigo = tirar_dado.invoke({ "dado": info_enemigo.get("dado_daño", "1d6") })
            jugador["vida_actual"] = max(0, jugador["vida_actual"] - daño_enemigo)
            narracion.append(_narrar(f"{info_enemigo['nombre']} ataca y te inflige {daño_enemigo} de daño. Vida restante: {jugador['vida_actual']}/{jugador['vida_max']}."))
            _guardar_jugador(jugador)
        else:
            narracion.append(_narrar(f"{info_enemigo['nombre']} ataca pero falla."))
    if jugador["vida_actual"] <= 0:
        narracion.append(_narrar(f"{jugador['nombre']} cae derrotado. Narra su caída."))
        estado_final = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
        return _respuesta_turno(jugador, estado_final, "\n\n".join(narracion), "derrota", tirada_enemigo)

    estado_final = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    return _respuesta_turno(jugador, estado_final, "\n\n".join(narracion), None, tirada)


def combate(entidades_presentes: list) -> str:
    jugador = _cargar_jugador()

    if not entidades_presentes:
        return "victoria"

    nombres = ", ".join( # Incluimos arma y descripción: sin esto el LLM inventa armas (ej. "garras" para una flautista)
        f"{e['nombre']} [arma: {e.get('arma') or '?'}, descripción: {e.get('descripcion', '')}] (AC:{e.get('ac', 10)}, HP:{e.get('vida_actual', '?')})"
        for e in entidades_presentes
    )
    arma_jugador = jugador.get("arma", {}).get("nombre", "sus puños")
    return _narrar(
        f"El jugador ({jugador['nombre']}, armado con {arma_jugador}) se enfrenta a: {nombres}. "
        f"Describe cómo irrumpe el combate de forma brusca e imprevista, respetando arma y descripción de cada entidad. "
        f"No resuelvas ningún ataque todavía."
    )