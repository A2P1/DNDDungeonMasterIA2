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
    system_prompt_combate = f.read().strip()


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
        if e["id"] == entidad_id:
            return "enemigo"
    for n in entidades.get("npcs", []):
        if n["id"] == entidad_id:
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


def _contexto_escena_msgs() -> list: # Beat + diario como SystemMessages para que el LLM de combate respete la ubicación, los NPCs y los hechos ya establecidos
    raw_beat = get_siguiente_beat.invoke({})
    if raw_beat == "CAMPAÑA COMPLETADA":
        beat_msg = SystemMessage(content="BEAT ACTUAL: campaña completada.")
    else:
        beat_msg = SystemMessage(content=f"BEAT ACTUAL (escena en la que ocurre el combate, respeta lugar y NPCs):\n{raw_beat}")
    diario = cargar_diario()
    diario_msg = SystemMessage(content=f"DIARIO (memoria de la partida, NO contradigas lo establecido):\n{diario.model_dump_json(indent=2, exclude_none=True)}")
    return [beat_msg, diario_msg]


def _narrar(contexto: str) -> str:
    msgs = [
        SystemMessage(content=system_prompt_combate + "\n\nMODO: NARRAR"),
        *_contexto_escena_msgs(), # Inyectamos beat + diario para que el combate no invente ubicación ni mezcle el nombre del jugador con NPCs
        HumanMessage(content=contexto)
    ]
    return llm.invoke(msgs).content


def _evaluar_accion(accion: str, contexto_combate: str) -> dict:
    try:
        evaluacion = llm_evaluar.invoke([
            SystemMessage(content=system_prompt_combate + "\n\nMODO: EVALUAR ACCIÓN"),
            HumanMessage(content=f"Contexto del combate:\n{contexto_combate}\n\nAcción del jugador: {accion}")
        ])
        return evaluacion.model_dump(exclude_none=True)
    except Exception:
        return {"viable": False, "razon": "No se pudo interpretar la acción"}


def _get_vivos(entidades: list) -> list:
    vivos = []
    for e in entidades:
        info_raw = get_info_entidad.invoke({"entidad_id": e["id"]})
        try:
            info = json.loads(info_raw)
            if info.get("estado") == "vivo":
                info["tipo_entidad"] = e.get("tipo_entidad", "enemigo")
                vivos.append(info)
        except (json.JSONDecodeError, TypeError):
            pass
    return vivos


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
    narracion = []
    tiro = None

    estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    enemigos_vivos = estado.get("enemigos_vivos", [])

    if not enemigos_vivos:
        return _respuesta_turno(jugador, estado, "No quedan enemigos.", "victoria", tiro)

    armas_inv = get_armas(jugador)
    if armas_inv:
        verificacion = verificar_arma_en_accion(accion, armas_inv)
        if verificacion["estado"] == "no_en_inventario":
            nombres_armas = ", ".join(a["nombre"] for a in armas_inv)
            texto = _narrar(
                f"El jugador intenta usar '{verificacion['nombre']}' pero no lo tiene. "
                f"Sus armas son: {nombres_armas}. Narra que no tiene esa arma."
            )
            return _respuesta_turno(jugador, estado, texto, None, tiro)
        elif verificacion["estado"] == "encontrada":
            jugador["arma"] = verificacion["arma"]
            _guardar_jugador(jugador)

    arma_actual = jugador.get("arma", {})
    consumibles = [i for i in jugador.get("inventario", []) if i.get("tipo") == "consumible"]
    contexto = (
        f"Jugador: {jugador['nombre']} ({jugador.get('clase', '?')}), "
        f"Arma: {arma_actual.get('nombre', 'sus puños')} (dado: {arma_actual.get('dado_daño', '1d6')}), "
        f"Atributos: {json.dumps(jugador.get('atributos', {}))}\n"
        f"Consumibles disponibles: {json.dumps(consumibles, ensure_ascii=False)}\n"
        f"Enemigos vivos: {json.dumps(enemigos_vivos, ensure_ascii=False)}"
    )
    evaluacion = _evaluar_accion(accion, contexto)

    if not evaluacion.get("viable", False):
        razon = evaluacion.get("razon", "Eso no es posible aquí.")
        texto = _narrar(f"El jugador intenta: '{accion}'. No es viable: {razon}")
        return _respuesta_turno(jugador, estado, texto, None, tiro)

    tipo = evaluacion.get("tipo", "accion")
    atributo = evaluacion.get("atributo", "fue")
    dc = evaluacion.get("dc", 12)
    mod = jugador.get("atributos", {}).get(atributo, 0)

    # Para ataques, sobreescribimos dc con la AC real del objetivo (más fiable que confiar en el LLM)
    if evaluacion.get("tipo") == "ataque":
        objetivo_id_para_ac = evaluacion.get("objetivo") or (enemigos_vivos[0]["id"] if enemigos_vivos else None)
        if objetivo_id_para_ac:
            try:
                info_obj = json.loads(get_info_entidad.invoke({"entidad_id": objetivo_id_para_ac}))
                dc = info_obj.get("ac", dc) # si no hay ac válido, mantenemos el dc del LLM
            except (json.JSONDecodeError, TypeError):
                pass # si la consulta falla, mantenemos el dc del LLM como red de seguridad

    ventaja_enemigos = False

    item_name = evaluacion.get("usa_item")
    if item_name:
        resultado_item = usar_item.invoke({"nombre_item": item_name})
        jugador = _cargar_jugador()
        narracion.append(_narrar(
            f"El jugador usa '{item_name}'. Resultado: {resultado_item}. Narra el uso del item con color."
        ))
    else:
        tirada = tirar_d20.invoke({})
        if jugador.get("ventaja_proximo_turno"): # Si en el turno anterior un enemigo pifió, el jugador ataca con ventaja: tira 2d20 y se queda con la mejor
            tirada = max(tirada, tirar_d20.invoke({}))
            jugador["ventaja_proximo_turno"] = False # Consumimos el flag para que solo aplique a este ataque
            _guardar_jugador(jugador)
        critico = (tirada == 20 and tipo == "ataque")
        pifia = (tirada == 1)
        total = tirada + mod
        tiro = tirada
        if pifia:
            ventaja_enemigos = True
            narracion.append(_narrar(
                f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                f"NAT 1. ¡PIFIA! El ataque falla estrepitosamente y el jugador queda expuesto. "
                f"Narra una complicación dramática y memorable, siendo creativo: puede involucrar al entorno, a los enemigos cercanos, "
                f"a objetos del lugar o cualquier cosa que tenga sentido en la escena. Evita repetir el mismo tipo de complicación cada vez."
            ))
        elif critico or total >= dc:
            if evaluacion.get("termina_combate"):
                motivo = evaluacion.get("motivo_fin", "el combate termina por una resolución narrativa")
                texto = _narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. ÉXITO. "
                    f"El combate termina: {motivo}. Narra el desenlace con tensión."
                )
                return _respuesta_turno(jugador, estado, texto, "resolucion", tiro)

            dado_daño = evaluacion.get("dado_daño")
            if dado_daño:
                if critico:
                    partes = dado_daño.lower().split("d")
                    cantidad = int(partes[0])
                    caras = int(partes[1])
                    daño = (cantidad * caras) + mod
                else:
                    daño = tirar_dado.invoke({"dado": dado_daño}) + mod
                daño = max(1, daño)

                objetivo_id = evaluacion.get("objetivo")
                if not objetivo_id and enemigos_vivos:
                    objetivo_id = enemigos_vivos[0]["id"]
                if objetivo_id:
                    tipo_entidad = _get_tipo_entidad(objetivo_id)
                    if tipo_entidad == "npc":
                        resultado = json.loads(dañar_npc.invoke({"npc_id": objetivo_id, "daño": daño}))
                    else:
                        resultado = json.loads(dañar_enemigo.invoke({"enemigo_id": objetivo_id, "daño": daño}))
                    msg_daño = resultado["mensaje"]
                else:
                    msg_daño = "No hay objetivo al que aplicar el daño."

                narracion.append(_narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. "
                    f"{'¡CRÍTICO! ' if critico else ''}ÉXITO. Daño: {daño}. {msg_daño}"
                ))
            else:
                efecto = evaluacion.get("efecto_exito", "")
                narracion.append(_narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. ÉXITO. Efecto: {efecto}"
                ))
        else:
            efecto = evaluacion.get("efecto_fallo", "")
            narracion.append(_narrar(
                f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                f"{tirada}+{mod}={total} vs DC {dc}. FALLO. Efecto: {efecto}"
            ))

    estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    if estado["combate_terminado"]:
        narracion.append(_narrar("Todos los enemigos han caído. El jugador ha ganado el combate."))
        return _respuesta_turno(jugador, estado, "\n\n".join(narracion), "victoria", tiro)

    for e_resumen in estado.get("enemigos_vivos", [])[:2]:
        info = json.loads(get_info_entidad.invoke({"entidad_id": e_resumen["id"]}))
        atributo_ataque = info.get("atributo_ataque", "fue")
        if atributo_ataque not in ("fue", "des", "int"):
            atributo_ataque = "fue"
        mod_enemigo = info.get("atributos", {}).get(atributo_ataque, 0)
        tirada_enemigo = tirar_d20.invoke({})
        if ventaja_enemigos:
            tirada_enemigo = max(tirada_enemigo, tirar_d20.invoke({}))
        critico_enemigo = (tirada_enemigo == 20)
        pifia_enemigo = (tirada_enemigo == 1)
        total_enemigo = tirada_enemigo + mod_enemigo

        if pifia_enemigo:
            jugador["ventaja_proximo_turno"] = True # Simetría con el jugador: la pifia enemiga deja al jugador en posición ventajosa para su siguiente ataque
            _guardar_jugador(jugador)
            narracion.append(_narrar(
                f"{info['nombre']} intenta atacar con {info.get('arma', 'sus garras')}. "
                f"NAT 1. ¡PIFIA! Narra una complicación dramática y memorable, siendo creativo: puede involucrar al entorno, "
                f"a sus aliados, a objetos del lugar o a su propio cuerpo. Evita repetir el mismo tipo de complicación cada vez. "
                f"El jugador queda en posición ventajosa para responder."
            ))
        elif critico_enemigo or total_enemigo >= jugador["ac"]:
            dado = info.get("dado_daño", "1d4")
            if critico_enemigo:
                partes = dado.lower().split("d")
                cantidad = int(partes[0])
                caras = int(partes[1])
                daño_enemigo = (cantidad * caras) + mod_enemigo
            else:
                daño_enemigo = tirar_dado.invoke({"dado": dado}) + mod_enemigo
            daño_enemigo = max(1, daño_enemigo)
            jugador["vida_actual"] = max(0, jugador["vida_actual"] - daño_enemigo)
            _guardar_jugador(jugador)
            narracion.append(_narrar(
                f"{info['nombre']} ataca al jugador con {info.get('arma', 'sus garras')}. "
                f"Tirada: {tirada_enemigo}+{mod_enemigo}={total_enemigo} vs AC {jugador['ac']} ({atributo_ataque.upper()}). "
                f"{'¡CRÍTICO! ' if critico_enemigo else ''}ACIERTA. Daño: {daño_enemigo}. Vida jugador: {jugador['vida_actual']}/{jugador['vida_max']}"
            ))
        else:
            narracion.append(_narrar(
                f"{info['nombre']} ataca al jugador con {info.get('arma', 'sus garras')}. "
                f"Tirada: {tirada_enemigo}+{mod_enemigo}={total_enemigo} vs AC {jugador['ac']} ({atributo_ataque.upper()}). FALLA."
            ))

    if jugador["vida_actual"] <= 0:
        narracion.append(_narrar(f"{jugador['nombre']} cae derrotado. Narra su caída."))
        estado_final = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
        return _respuesta_turno(jugador, estado_final, "\n\n".join(narracion), "derrota", tiro)

    estado_final = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    return _respuesta_turno(jugador, estado_final, "\n\n".join(narracion), None, tiro)


def combate(entidades_presentes: list) -> str:
    jugador = _cargar_jugador()

    if not entidades_presentes:
        return "victoria"

    nombres = ", ".join(
        f"{e['nombre']} (AC:{e.get('ac', 10)}, HP:{e.get('vida_actual', '?')})"
        for e in entidades_presentes
    )
    arma_jugador = jugador.get("arma", {}).get("nombre", "sus puños")
    return _narrar(
        f"El jugador ({jugador['nombre']}, armado con {arma_jugador}) se enfrenta a: {nombres}. "
        f"Describe cómo irrumpe el combate de forma brusca e imprevista, presentando a los enemigos y la tensión del momento. "
        f"No resuelvas ningún ataque todavía."
    )