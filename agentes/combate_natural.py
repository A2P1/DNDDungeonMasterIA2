import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from tools.entidades import dañar_enemigo, dañar_npc, get_info_entidad
from tools.dados import tirar_d20, tirar_dado
from config import STATS_PATH, COMBATE_PROMPT_PATH, MODEL_NAME
from ui import combate_msg, enemigo_msg, estado_combate, victoria_msg, derrota_msg, prompt_jugador

load_dotenv()

with open(COMBATE_PROMPT_PATH, 'r', encoding='utf-8') as f:
    system_prompt_combate = f.read().strip()

llm = ChatOpenAI(model=MODEL_NAME, temperature=0.9)
llm_evaluar = ChatOpenAI(model=MODEL_NAME, temperature=0.3)
parser = JsonOutputParser()


def _modificador(valor: int) -> int:
    return valor


def _cargar_jugador() -> dict:
    if not STATS_PATH.exists():
        return {}
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _guardar_jugador(jugador: dict):
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(jugador, f, indent=2, ensure_ascii=False)


def _narrar(contexto: str) -> str:
    respuesta = llm.invoke([
        SystemMessage(content=system_prompt_combate + "\n\nMODO: NARRAR"),
        HumanMessage(content=contexto)
    ])
    return respuesta.content


def _evaluar_accion(accion: str, contexto_combate: str) -> dict:
    respuesta = llm_evaluar.invoke([
        SystemMessage(content=system_prompt_combate + "\n\nMODO: EVALUAR ACCIÓN"),
        HumanMessage(content=f"Contexto del combate:\n{contexto_combate}\n\nAcción del jugador: {accion}")
    ])
    try:
        return parser.parse(respuesta.content)
    except Exception:
        return {"viable": False, "razon": "No se pudo interpretar la acción"}


def _get_vivos(entidades: list) -> list:
    """Re-consulta entidades.json para obtener el estado actual de cada entidad."""
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


def _mostrar_estado_natural(jugador: dict, entidades: list):
    vivos = _get_vivos(entidades)
    enemigos_str = ", ".join(
        f"{e['nombre']} ({e['vida_actual']}/{e['vida_max']})" for e in vivos
    )
    estado_combate(jugador['vida_actual'], jugador['vida_max'], enemigos_str)


def combate_natural(entidades_presentes: list) -> str:
    """Ejecuta un combate iniciado por el jugador fuera de un beat de combate.

    entidades_presentes: lista de dicts con campos del entity JSON más 'tipo_entidad'
                         ("enemigo" | "npc") para saber qué tool de daño usar.

    Returns:
        "victoria" o "derrota"
    """
    jugador = _cargar_jugador()

    if not entidades_presentes:
        return "victoria"

    # Narrar inicio del enfrentamiento inesperado
    nombres = ", ".join(
        f"{e['nombre']} (AC:{e.get('ac', 10)}, HP:{e.get('vida_actual', '?')})"
        for e in entidades_presentes
    )
    arma_jugador = jugador.get("arma", {}).get("nombre", "sus puños")
    combate_msg(_narrar(
        f"El jugador ({jugador['nombre']}, armado con {arma_jugador}) inicia un ataque inesperado contra: {nombres}. "
        f"Describe cómo irrumpe el combate de forma brusca e imprevista."
    ))
    _mostrar_estado_natural(jugador, entidades_presentes)

    while True:
        # === TURNO DEL JUGADOR ===
        accion = prompt_jugador()

        if not accion:
            continue

        vivos = _get_vivos(entidades_presentes)

        if not vivos:
            break

        contexto = (
            f"Jugador: {jugador['nombre']} ({jugador.get('clase', '?')}), "
            f"Arma: {arma_jugador} (dado: {jugador.get('arma', {}).get('dado_daño', '1d6')}), "
            f"Atributos: {json.dumps(jugador.get('atributos', {}))}\n"
            f"Entidades presentes (vivas): {json.dumps(vivos, ensure_ascii=False)}"
        )

        evaluacion = _evaluar_accion(accion, contexto)

        if not evaluacion.get("viable", False):
            razon = evaluacion.get("razon", "Eso no es posible aquí.")
            combate_msg(_narrar(f"El jugador intenta: '{accion}'. No es viable: {razon}"))
            continue

        tipo = evaluacion.get("tipo", "accion")
        atributo = evaluacion.get("atributo", "fue")
        dc = evaluacion.get("dc", 12)
        mod = _modificador(jugador.get("atributos", {}).get(atributo, 0))

        tirada = tirar_d20.invoke({})
        critico = (tirada == 20 and tipo == "ataque")
        total = tirada + mod

        if critico or total >= dc:
            dado_daño = evaluacion.get("dado_daño")
            objetivo_id = evaluacion.get("objetivo")

            if dado_daño:
                daño = tirar_dado.invoke({"dado": dado_daño}) + mod
                if critico:
                    daño += tirar_dado.invoke({"dado": dado_daño})
                daño = max(1, daño)

                if objetivo_id:
                    entidad_objetivo = next(
                        (e for e in entidades_presentes if e["id"] == objetivo_id), None
                    )
                    tipo_entidad = entidad_objetivo.get("tipo_entidad", "enemigo") if entidad_objetivo else "enemigo"
                    if tipo_entidad == "npc":
                        resultado = json.loads(dañar_npc.invoke({"npc_id": objetivo_id, "daño": daño}))
                    else:
                        resultado = json.loads(dañar_enemigo.invoke({"enemigo_id": objetivo_id, "daño": daño}))
                    msg_daño = resultado["mensaje"]
                else:
                    msg_daño = ""
                    for e in vivos:
                        if e.get("tipo_entidad") == "npc":
                            resultado = json.loads(dañar_npc.invoke({"npc_id": e["id"], "daño": daño}))
                        else:
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
            efecto = evaluacion.get("efecto_fallo", "")
            combate_msg(_narrar(
                f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                f"{tirada}+{mod}={total} vs DC {dc}. FALLO. Efecto: {efecto}"
            ))

        # === CHECK VICTORIA ===
        vivos_actual = _get_vivos(entidades_presentes)
        if not vivos_actual:
            victoria_msg(_narrar(
                f"Todas las entidades han caído. El jugador triunfa en este enfrentamiento inesperado."
            ))
            return "victoria"

        # === TURNO DE LAS ENTIDADES (contraataque) ===
        for e in vivos_actual:
            info_raw = get_info_entidad.invoke({"entidad_id": e["id"]})
            try:
                info = json.loads(info_raw)
            except (json.JSONDecodeError, TypeError):
                continue

            mod_fue = _modificador(info.get("atributos", {}).get("fue", 2))
            tirada_enemigo = tirar_d20.invoke({})
            total_enemigo = tirada_enemigo + mod_fue

            if total_enemigo >= jugador["ac"]:
                daño_enemigo = tirar_dado.invoke({"dado": info.get("dado_daño", "1d4")}) + mod_fue
                daño_enemigo = max(1, daño_enemigo)
                jugador["vida_actual"] = max(0, jugador["vida_actual"] - daño_enemigo)
                _guardar_jugador(jugador)

                enemigo_msg(info['nombre'], _narrar(
                    f"{info['nombre']} contraataca al jugador con {info.get('arma', 'sus manos')}. "
                    f"Tirada: {tirada_enemigo}+{mod_fue}={total_enemigo} vs AC {jugador['ac']}. "
                    f"ACIERTA. Daño: {daño_enemigo}. "
                    f"Vida jugador: {jugador['vida_actual']}/{jugador['vida_max']}"
                ))
            else:
                enemigo_msg(info['nombre'], _narrar(
                    f"{info['nombre']} intenta contraatacar al jugador. "
                    f"Tirada: {tirada_enemigo}+{mod_fue}={total_enemigo} vs AC {jugador['ac']}. FALLA."
                ))

        # === CHECK DERROTA ===
        if jugador["vida_actual"] <= 0:
            derrota_msg(_narrar(
                f"{jugador['nombre']} cae con {jugador['vida_actual']} HP en un enfrentamiento imprevisto. "
                f"Narra su caída."
            ))
            return "derrota"

        _mostrar_estado_natural(jugador, entidades_presentes)
