import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from tools.entidades import dañar_enemigo, get_enemigos_beat, get_estado_combate, get_info_entidad
from tools.dados import tirar_d20, tirar_dado
from tools.inventario import get_armas, verificar_arma_en_accion
from config import STATS_PATH, COMBATE_PROMPT_PATH, MODEL_NAME
from ui import combate_msg, enemigo_msg, estado_combate, victoria_msg, derrota_msg, prompt_jugador, sistema_msg

load_dotenv()


with open(COMBATE_PROMPT_PATH, 'r', encoding='utf-8') as f:
    system_prompt_combate = f.read().strip()

llm = ChatOpenAI(model=MODEL_NAME, temperature=0.9)
llm_evaluar = ChatOpenAI(model=MODEL_NAME, temperature=0.3)
parser = JsonOutputParser()



def _modificador(valor: int) -> int:
    """Devuelve el valor del atributo directamente (sistema 0-5)."""
    return valor

"""Carga la ficha del jugador con sus estadísticas"""
def _cargar_jugador() -> dict: 
    if not STATS_PATH.exists():
        return {}
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

"""Guarda los datos del jugador después de un combate"""
def _guardar_jugador(jugador: dict):
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(jugador, f, indent=2, ensure_ascii=False)

"""Narra lo que sucede en un combate"""
def _narrar(contexto: str) -> str:
    """LLM narra un evento de combate en modo NARRAR."""
    respuesta = llm.invoke([
        SystemMessage(content=system_prompt_combate + "\n\nMODO: NARRAR"),
        HumanMessage(content=contexto)
    ])
    return respuesta.content

"""Evalúa si la acción que quiere realizar el jugador es viable en el contexto actual"""
def _evaluar_accion(accion: str, contexto_combate: str) -> dict:
    """LLM evalúa cualquier acción del jugador. Devuelve dict con tipo, atributo, dc, etc."""
    respuesta = llm_evaluar.invoke([
        SystemMessage(content=system_prompt_combate + "\n\nMODO: EVALUAR ACCIÓN"),
        HumanMessage(content=f"Contexto del combate:\n{contexto_combate}\n\nAcción del jugador: {accion}")
    ])
    try:
        return parser.parse(respuesta.content)
    except Exception:
        return {"viable": False, "razon": "No se pudo interpretar la acción"}

"""Muestra el estado actual del combate: vida del jugador, enemigos vivos y su vida."""
def _mostrar_estado(jugador: dict, beat_id: str):
    """Muestra el estado actual del combate."""
    estado_raw = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    enemigos_str = ", ".join(
        f"{e['nombre']} ({e['vida']})" for e in estado_raw.get("enemigos_vivos", [])
    )
    estado_combate(jugador['vida_actual'], jugador['vida_max'], enemigos_str)




def _respuesta_turno(jugador: dict, estado: dict, narracion: str, resultado) -> dict:
    """Construye el dict de respuesta estándar para un turno de combate."""
    return {
        "narracion": narracion,
        "jugador_vida": jugador["vida_actual"],
        "jugador_vida_max": jugador["vida_max"],
        "entidades_vivas": estado.get("enemigos_vivos", []),
        "combate_terminado": estado.get("combate_terminado", False),
        "resultado": resultado
    }


def procesar_turno(beat_id: str, accion: str) -> dict:
    """Procesa un turno completo de combate (jugador + enemigos) para la API.
    No bloquea ni usa terminal. Devuelve el estado y la narración del turno."""
    jugador = _cargar_jugador()
    narracion = []

    estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    enemigos_vivos = estado.get("enemigos_vivos", [])

    if not enemigos_vivos:
        return _respuesta_turno(jugador, estado, "No quedan enemigos.", "victoria")

    # Verificar si el jugador menciona un arma que no tiene
    armas_inv = get_armas(jugador)
    if armas_inv:
        verificacion = verificar_arma_en_accion(accion, armas_inv)
        if verificacion["estado"] == "no_en_inventario":
            nombres_armas = ", ".join(a["nombre"] for a in armas_inv)
            texto = _narrar(
                f"El jugador intenta usar '{verificacion['nombre']}' pero no lo tiene. "
                f"Sus armas son: {nombres_armas}. Narra que no tiene esa arma."
            )
            return _respuesta_turno(jugador, estado, texto, None)
        elif verificacion["estado"] == "encontrada":
            jugador["arma"] = verificacion["arma"]

    # Construir contexto y evaluar la acción
    arma_actual = jugador.get("arma", {})
    contexto = (
        f"Jugador: {jugador['nombre']} ({jugador.get('clase', '?')}), "
        f"Arma: {arma_actual.get('nombre', 'sus puños')} (dado: {arma_actual.get('dado_daño', '1d6')}), "
        f"Atributos: {json.dumps(jugador.get('atributos', {}))}\n"
        f"Enemigos vivos: {json.dumps(enemigos_vivos, ensure_ascii=False)}"
    )
    evaluacion = _evaluar_accion(accion, contexto)

    if not evaluacion.get("viable", False):
        razon = evaluacion.get("razon", "Eso no es posible aquí.")
        texto = _narrar(f"El jugador intenta: '{accion}'. No es viable: {razon}")
        return _respuesta_turno(jugador, estado, texto, None)

    tipo = evaluacion.get("tipo", "accion")
    atributo = evaluacion.get("atributo", "fue")
    dc = evaluacion.get("dc", 12)
    mod = _modificador(jugador.get("atributos", {}).get(atributo, 10))

    tirada = tirar_d20.invoke({})
    critico = (tirada == 20 and tipo == "ataque")
    total = tirada + mod

    if critico or total >= dc:
        dado_daño = evaluacion.get("dado_daño")
        if dado_daño:
            daño = tirar_dado.invoke({"dado": dado_daño}) + mod
            if critico:
                daño += tirar_dado.invoke({"dado": dado_daño})
            daño = max(1, daño)

            objetivo_id = evaluacion.get("objetivo")
            if objetivo_id:
                resultado_daño = json.loads(dañar_enemigo.invoke({"enemigo_id": objetivo_id, "daño": daño}))
                msg_daño = resultado_daño["mensaje"]
            else:
                msg_daño = ""
                for e in enemigos_vivos:
                    resultado_daño = json.loads(dañar_enemigo.invoke({"enemigo_id": e["id"], "daño": daño}))
                    msg_daño += resultado_daño["mensaje"] + " "

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

    # Check victoria tras el ataque del jugador
    estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    if estado["combate_terminado"]:
        narracion.append(_narrar("Todos los enemigos han caído. El jugador ha ganado el combate."))
        return _respuesta_turno(jugador, estado, "\n\n".join(narracion), "victoria")

    # Turno de los enemigos
    for e_resumen in estado.get("enemigos_vivos", []):
        info = json.loads(get_info_entidad.invoke({"entidad_id": e_resumen["id"]}))
        mod_fue_enemigo = _modificador(info.get("atributos", {}).get("fue", 10))
        tirada_enemigo = tirar_d20.invoke({})
        total_enemigo = tirada_enemigo + mod_fue_enemigo

        if total_enemigo >= jugador["ac"]:
            daño_enemigo = tirar_dado.invoke({"dado": info["dado_daño"]}) + mod_fue_enemigo
            daño_enemigo = max(1, daño_enemigo)
            jugador["vida_actual"] = max(0, jugador["vida_actual"] - daño_enemigo)
            _guardar_jugador(jugador)
            narracion.append(_narrar(
                f"{info['nombre']} ataca al jugador con {info.get('arma', 'sus garras')}. "
                f"Tirada: {tirada_enemigo}+{mod_fue_enemigo}={total_enemigo} vs AC {jugador['ac']}. "
                f"ACIERTA. Daño: {daño_enemigo}. Vida jugador: {jugador['vida_actual']}/{jugador['vida_max']}"
            ))
        else:
            narracion.append(_narrar(
                f"{info['nombre']} ataca al jugador con {info.get('arma', 'sus garras')}. "
                f"Tirada: {tirada_enemigo}+{mod_fue_enemigo}={total_enemigo} vs AC {jugador['ac']}. FALLA."
            ))

    # Check derrota
    if jugador["vida_actual"] <= 0:
        narracion.append(_narrar(f"{jugador['nombre']} cae derrotado. Narra su caída."))
        estado_final = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
        return _respuesta_turno(jugador, estado_final, "\n\n".join(narracion), "derrota")

    estado_final = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    return _respuesta_turno(jugador, estado_final, "\n\n".join(narracion), None)


def combate(beat_id: str) -> str:
    """Ejecuta el loop de combate para un beat.
    """
    # Cargar enemigos y jugador
    enemigos_raw = get_enemigos_beat.invoke({"beat_id": beat_id})
    try:
        enemigos = json.loads(enemigos_raw)
    except (json.JSONDecodeError, TypeError):
        enemigos = []

    jugador = _cargar_jugador()

    if not enemigos:
        return "victoria"

    arma_turno = None 

    # Narrar inicio
    nombres = ", ".join(f"{e['nombre']} (AC:{e['ac']}, HP:{e['vida_actual']})" for e in enemigos)
    arma_jugador = jugador.get("arma", {}).get("nombre", "sus puños")
    combate_msg(_narrar(
        f"El jugador ({jugador['nombre']}, armado con {arma_jugador}) se encuentra con: {nombres}. "
        f"Describe su aparición amenazante."
    ))
    _mostrar_estado(jugador, beat_id)

    while True:
        accion = prompt_jugador()

        if not accion:
            continue

        # Obtener enemigos vivos
        estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
        enemigos_vivos = estado.get("enemigos_vivos", [])

        if not enemigos_vivos:
            break

        """Evaluar el arma con el que quiere atacar el jugador"""
        armas_inv = get_armas(jugador)
        if armas_inv:
            verificacion = verificar_arma_en_accion(accion, armas_inv)
            if verificacion["estado"] == "no_en_inventario":
                nombres_armas = ", ".join(a["nombre"] for a in armas_inv)
                combate_msg(_narrar(
                    f"El jugador intenta usar '{verificacion['nombre']}' pero no lo tiene. "
                    f"Sus armas son: {nombres_armas}. Narra que no tiene esa arma."
                ))
                continue
            elif verificacion["estado"] == "encontrada":
                arma_turno = verificacion["arma"]
                jugador["arma"] = arma_turno

        """Se construye el contexto con el arma que quiere utilizar el jugador"""
        arma_actual = arma_turno or jugador.get("arma", {})
        contexto = (
            f"Jugador: {jugador['nombre']} ({jugador.get('clase', '?')}), "
            f"Arma: {arma_actual.get('nombre', 'sus puños')} (dado: {arma_actual.get('dado_daño', '1d6')}), "
            f"Atributos: {json.dumps(jugador.get('atributos', {}))}\n"
            f"Enemigos vivos: {json.dumps(enemigos_vivos, ensure_ascii=False)}"
        )

        """Se evalúa la acción"""
        evaluacion = _evaluar_accion(accion, contexto)

        if not evaluacion.get("viable", False):
            razon = evaluacion.get("razon", "Eso no es posible aquí.")
            combate_msg(_narrar(f"El jugador intenta: '{accion}'. No es viable: {razon}"))
            continue

        tipo = evaluacion.get("tipo", "accion")

        """Si el usuario quiere atacar pero no se ha especificado un arma todavía, se pide"""
        if tipo == "ataque" and armas_inv and arma_turno is None:
            nombres_armas = ", ".join(a["nombre"] for a in armas_inv)
            sistema_msg(f"¿Con qué arma atacas? Tienes: {nombres_armas}")
            eleccion = prompt_jugador()
            v2 = verificar_arma_en_accion(eleccion, armas_inv)
            if v2["estado"] == "encontrada":
                arma_turno = v2["arma"]
                jugador["arma"] = arma_turno
            else:
                combate_msg(f"No tienes esa arma. Armas disponibles: {nombres_armas}")
                continue

        if arma_turno:
            evaluacion["dado_daño"] = arma_turno.get("dado_daño", evaluacion.get("dado_daño", "1d6"))

        atributo = evaluacion.get("atributo", "fue")
        dc = evaluacion.get("dc", 12)
        mod = _modificador(jugador.get("atributos", {}).get(atributo, 10))


        tirada = tirar_d20.invoke({})
        critico = (tirada == 20 and tipo == "ataque")
        total = tirada + mod

        if critico or total >= dc:
            dado_daño = evaluacion.get("dado_daño")

            if dado_daño:
                daño = tirar_dado.invoke({"dado": dado_daño}) + mod
                if critico:
                    daño += tirar_dado.invoke({"dado": dado_daño})
                daño = max(1, daño)

                objetivo_id = evaluacion.get("objetivo")
                if objetivo_id:
                    resultado = json.loads(dañar_enemigo.invoke({"enemigo_id": objetivo_id, "daño": daño}))
                    msg_daño = resultado["mensaje"]
                else:
                    msg_daño = ""
                    for e in enemigos_vivos:
                        resultado = json.loads(dañar_enemigo.invoke({"enemigo_id": e["id"], "daño": daño}))
                        msg_daño += resultado["mensaje"] + " "

                combate_msg(_narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. "
                    f"{'¡CRÍTICO! ' if critico else ''}ÉXITO. Daño: {daño}. {msg_daño}"
                ))
            else:
                efecto = evaluacion.get("efecto_exito", "")
                combate_msg(_narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. ÉXITO. Efecto: {efecto}"
                ))
        else:
            # === FALLO ===
            efecto = evaluacion.get("efecto_fallo", "")
            combate_msg(_narrar(
                f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                f"{tirada}+{mod}={total} vs DC {dc}. FALLO. Efecto: {efecto}"
            ))

        # === CHECK VICTORIA ===
        estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
        if estado["combate_terminado"]:
            xp_total = sum(e.get("xp", 0) for e in enemigos)
            victoria_msg(_narrar(f"Todos los enemigos han caído. El jugador obtiene {xp_total} XP."))
            return "victoria"

        # === TURNO DE LOS ENEMIGOS ===
        enemigos_vivos = estado.get("enemigos_vivos", [])
        for e_resumen in enemigos_vivos:
            info = json.loads(get_info_entidad.invoke({"entidad_id": e_resumen["id"]}))
            mod_fue_enemigo = _modificador(info.get("atributos", {}).get("fue", 10))

            tirada_enemigo = tirar_d20.invoke({})
            total_enemigo = tirada_enemigo + mod_fue_enemigo

            if total_enemigo >= jugador["ac"]:
                daño_enemigo = tirar_dado.invoke({"dado": info["dado_daño"]}) + mod_fue_enemigo
                daño_enemigo = max(1, daño_enemigo)
                jugador["vida_actual"] = max(0, jugador["vida_actual"] - daño_enemigo)
                _guardar_jugador(jugador)

                enemigo_msg(info['nombre'], _narrar(
                    f"{info['nombre']} ataca al jugador con {info.get('arma', 'sus garras')}. "
                    f"Tirada: {tirada_enemigo}+{mod_fue_enemigo}={total_enemigo} vs AC {jugador['ac']}. "
                    f"ACIERTA. Daño: {daño_enemigo}. "
                    f"Vida jugador: {jugador['vida_actual']}/{jugador['vida_max']}"
                ))
            else:
                enemigo_msg(info['nombre'], _narrar(
                    f"{info['nombre']} ataca al jugador con {info.get('arma', 'sus garras')}. "
                    f"Tirada: {tirada_enemigo}+{mod_fue_enemigo}={total_enemigo} vs AC {jugador['ac']}. FALLA."
                ))

        # === CHECK DERROTA ===
        if jugador["vida_actual"] <= 0:
            derrota_msg(_narrar(
                f"{jugador['nombre']} cae con {jugador['vida_actual']} HP. "
                f"Narra su derrota."
            ))
            return "derrota"

        # Mostrar estado para el siguiente turno
        _mostrar_estado(jugador, beat_id)
