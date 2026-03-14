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
from config import STATS_PATH, COMBATE_PROMPT_PATH, MODEL_NAME

load_dotenv()

# Leer prompt de combate
with open(COMBATE_PROMPT_PATH, 'r', encoding='utf-8') as f:
    system_prompt_combate = f.read().strip()

llm = ChatOpenAI(model=MODEL_NAME, temperature=0.9)
llm_evaluar = ChatOpenAI(model=MODEL_NAME, temperature=0.3)
parser = JsonOutputParser()


# === UTILIDADES ===

def _modificador(valor: int) -> int:
    """Devuelve el valor del atributo directamente (sistema 0-5)."""
    return valor


def _cargar_jugador() -> dict:
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _guardar_jugador(jugador: dict):
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(jugador, f, indent=2, ensure_ascii=False)


def _narrar(contexto: str) -> str:
    """LLM narra un evento de combate en modo NARRAR."""
    respuesta = llm.invoke([
        SystemMessage(content=system_prompt_combate + "\n\nMODO: NARRAR"),
        HumanMessage(content=contexto)
    ])
    return respuesta.content


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


def _mostrar_estado(jugador: dict, beat_id: str):
    """Muestra el estado actual del combate."""
    estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    enemigos_str = ", ".join(
        f"{e['nombre']} ({e['vida']})" for e in estado.get("enemigos_vivos", [])
    )
    print(f"\n[Tu vida: {jugador['vida_actual']}/{jugador['vida_max']} | Enemigos: {enemigos_str}]\n")


# === COMBATE PRINCIPAL ===

def combate(beat_id: str) -> str:
    """Ejecuta el loop de combate para un beat.

    Returns:
        "victoria" o "derrota"
    """
    print("Estamos en combate")
    # Cargar enemigos y jugador
    enemigos_raw = get_enemigos_beat.invoke({"beat_id": beat_id})
    try:
        enemigos = json.loads(enemigos_raw)
    except (json.JSONDecodeError, TypeError):
        enemigos = []

    jugador = _cargar_jugador()

    if not enemigos:
        return "victoria"

    # Narrar inicio
    nombres = ", ".join(f"{e['nombre']} (AC:{e['ac']}, HP:{e['vida_actual']})" for e in enemigos)
    arma_jugador = jugador.get("arma", {}).get("nombre", "sus puños")
    print(_narrar(
        f"El jugador ({jugador['nombre']}, armado con {arma_jugador}) se encuentra con: {nombres}. "
        f"Describe su aparición amenazante."
    ))
    _mostrar_estado(jugador, beat_id)

    while True:
        # === TURNO DEL JUGADOR ===
        accion = input("¿Qué haces? > ").strip()

        if not accion:
            continue

        # Obtener enemigos vivos
        estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
        enemigos_vivos = estado.get("enemigos_vivos", [])

        if not enemigos_vivos:
            break

        # Construir contexto para el LLM evaluador
        contexto = (
            f"Jugador: {jugador['nombre']} ({jugador.get('clase', '?')}), "
            f"Arma: {arma_jugador} (dado: {jugador.get('arma', {}).get('dado_daño', '1d6')}), "
            f"Atributos: {json.dumps(jugador.get('atributos', {}))}\n"
            f"Enemigos vivos: {json.dumps(enemigos_vivos, ensure_ascii=False)}"
        )

        # === TODO pasa por el LLM evaluador ===
        evaluacion = _evaluar_accion(accion, contexto)

        if not evaluacion.get("viable", False):
            razon = evaluacion.get("razon", "Eso no es posible aquí.")
            print(_narrar(f"El jugador intenta: '{accion}'. No es viable: {razon}"))
            continue

        tipo = evaluacion.get("tipo", "accion")
        atributo = evaluacion.get("atributo", "fue")
        dc = evaluacion.get("dc", 12)
        mod = _modificador(jugador.get("atributos", {}).get(atributo, 10))

        # Tirada d20 + modificador (usando tool)
        tirada = tirar_d20.invoke({})
        critico = (tirada == 20 and tipo == "ataque")
        total = tirada + mod

        if critico or total >= dc:
            # === ÉXITO ===
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

                print(_narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. "
                    f"{'¡CRÍTICO! ' if critico else ''}ÉXITO. Daño: {daño}. {msg_daño}"
                ))
            else:
                efecto = evaluacion.get("efecto_exito", "")
                print(_narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. ÉXITO. Efecto: {efecto}"
                ))
        else:
            # === FALLO ===
            efecto = evaluacion.get("efecto_fallo", "")
            print(_narrar(
                f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                f"{tirada}+{mod}={total} vs DC {dc}. FALLO. Efecto: {efecto}"
            ))

        # === CHECK VICTORIA ===
        estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
        if estado["combate_terminado"]:
            xp_total = sum(e.get("xp", 0) for e in enemigos)
            print(_narrar(f"Todos los enemigos han caído. El jugador obtiene {xp_total} XP."))
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

                print(_narrar(
                    f"{info['nombre']} ataca al jugador con {info.get('arma', 'sus garras')}. "
                    f"Tirada: {tirada_enemigo}+{mod_fue_enemigo}={total_enemigo} vs AC {jugador['ac']}. "
                    f"ACIERTA. Daño: {daño_enemigo}. "
                    f"Vida jugador: {jugador['vida_actual']}/{jugador['vida_max']}"
                ))
            else:
                print(_narrar(
                    f"{info['nombre']} ataca al jugador con {info.get('arma', 'sus garras')}. "
                    f"Tirada: {tirada_enemigo}+{mod_fue_enemigo}={total_enemigo} vs AC {jugador['ac']}. FALLA."
                ))

        # === CHECK DERROTA ===
        if jugador["vida_actual"] <= 0:
            print(_narrar(
                f"{jugador['nombre']} cae con {jugador['vida_actual']} HP. "
                f"Narra su derrota."
            ))
            return "derrota"

        # Mostrar estado para el siguiente turno
        _mostrar_estado(jugador, beat_id)
