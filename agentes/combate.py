import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from tools.entidades import dañar_enemigo, dañar_npc, get_info_entidad, get_estado_combate
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


def _modificador(valor: int) -> int: # El atributo (0-5) se usa directamente como modificador (Cosmere RPG)
    return valor


def _cargar_jugador() -> dict:
    """Carga la ficha del jugador con sus estadísticas."""
    if not STATS_PATH.exists():
        return {}
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _guardar_jugador(jugador: dict):
    """Guarda los datos del jugador después de un combate."""
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(jugador, f, indent=2, ensure_ascii=False)


def _narrar(contexto: str) -> str:
    """LLM narra un evento de combate."""
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


def _get_vivos(entidades: list) -> list:
    """Comprueba qué entidades de la lista siguen vivas consultando entidades.json."""
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


def _mostrar_estado(jugador: dict, entidades: list):
    """Muestra el estado actual del jugador y de los enemigos en la terminal."""
    vivos = _get_vivos(entidades)
    enemigos_str = ", ".join(
        f"{e['nombre']} ({e['vida_actual']}/{e['vida_max']})" for e in vivos
    )
    estado_combate(jugador['vida_actual'], jugador['vida_max'], enemigos_str)


# ── API ──────────────────────────────────────────────────────────────────────

def _respuesta_turno(jugador: dict, estado: dict, narracion: str, resultado) -> dict:
    """Construye el dict de respuesta estándar para un turno de combate (API)."""
    return {
        "narracion": narracion,
        "jugador_vida": jugador["vida_actual"],
        "jugador_vida_max": jugador["vida_max"],
        "entidades_vivas": estado.get("enemigos_vivos", []),
        "combate_terminado": estado.get("combate_terminado", False),
        "resultado": resultado
    }


def procesar_turno(beat_id: str, accion: str) -> dict:
    """Procesa un turno completo de combate (jugador + enemigos) para la API."""
    jugador = _cargar_jugador()
    narracion = []

    estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    enemigos_vivos = estado.get("enemigos_vivos", [])

    if not enemigos_vivos:
        return _respuesta_turno(jugador, estado, "No quedan enemigos.", "victoria")

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
    mod = _modificador(jugador.get("atributos", {}).get(atributo, 0))

    tirada = tirar_d20.invoke({})
    critico = (tirada == 20 and tipo == "ataque")
    pifia = (tirada == 1)
    total = tirada + mod

    if pifia:
        narracion.append(_narrar(
            f"Jugador: '{accion}'. Check de {atributo.upper()}: "
            f"NAT 1. ¡PIFIA! El ataque falla estrepitosamente. "
            f"Narra una complicación: el arma se atasca, el jugador tropieza, "
            f"se golpea a sí mismo o queda expuesto."
        ))
    elif critico or total >= dc:
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

    estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    if estado["combate_terminado"]:
        narracion.append(_narrar("Todos los enemigos han caído. El jugador ha ganado el combate."))
        return _respuesta_turno(jugador, estado, "\n\n".join(narracion), "victoria")

    for e_resumen in estado.get("enemigos_vivos", []):
        info = json.loads(get_info_entidad.invoke({"entidad_id": e_resumen["id"]}))
        mod_fue_enemigo = _modificador(info.get("atributos", {}).get("fue", 2))
        tirada_enemigo = tirar_d20.invoke({})
        total_enemigo = tirada_enemigo + mod_fue_enemigo

        if total_enemigo >= jugador["ac"]:
            daño_enemigo = tirar_dado.invoke({"dado": info.get("dado_daño", "1d4")}) + mod_fue_enemigo
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

    if jugador["vida_actual"] <= 0:
        narracion.append(_narrar(f"{jugador['nombre']} cae derrotado. Narra su caída."))
        estado_final = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
        return _respuesta_turno(jugador, estado_final, "\n\n".join(narracion), "derrota")

    estado_final = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    return _respuesta_turno(jugador, estado_final, "\n\n".join(narracion), None)


# ── CLI ──────────────────────────────────────────────────────────────────────

def combate(entidades_presentes: list) -> str:
    """Ejecuta el loop de combate para la terminal (CLI).
    Recibe la lista de entidades presentes en la escena."""
    jugador = _cargar_jugador()

    if not entidades_presentes:
        return "victoria"

    arma_turno = None

    nombres = ", ".join(
        f"{e['nombre']} (AC:{e.get('ac', 10)}, HP:{e.get('vida_actual', '?')})"
        for e in entidades_presentes
    )
    arma_jugador = jugador.get("arma", {}).get("nombre", "sus puños")
    combate_msg(_narrar(
        f"El jugador ({jugador['nombre']}, armado con {arma_jugador}) inicia un ataque inesperado contra: {nombres}. "
        f"Este primer ataque NO es certero, narra cómo el jugador falla o los enemigos esquivan. "
        f"Describe cómo irrumpe el combate de forma brusca e imprevista."
    ))
    _mostrar_estado(jugador, entidades_presentes)

    while True:
        accion = prompt_jugador()

        if not accion:
            continue

        vivos = _get_vivos(entidades_presentes)

        if not vivos:
            break

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

        arma_actual = arma_turno or jugador.get("arma", {})
        contexto = (
            f"Jugador: {jugador['nombre']} ({jugador.get('clase', '?')}), "
            f"Arma: {arma_actual.get('nombre', 'sus puños')} (dado: {arma_actual.get('dado_daño', '1d6')}), "
            f"Atributos: {json.dumps(jugador.get('atributos', {}))}\n"
            f"Entidades presentes (vivas): {json.dumps(vivos, ensure_ascii=False)}"
        )

        evaluacion = _evaluar_accion(accion, contexto)

        if not evaluacion.get("viable", False):
            razon = evaluacion.get("razon", "Eso no es posible aquí.")
            combate_msg(_narrar(f"El jugador intenta: '{accion}'. No es viable: {razon}"))
            continue

        tipo = evaluacion.get("tipo", "accion")

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
        mod = _modificador(jugador.get("atributos", {}).get(atributo, 0))

        tirada = tirar_d20.invoke({}) # Invocamos al dado de 20 caras para saber si golpea o no
        critico = (tirada == 20 and tipo == "ataque") # Nat 20 en ataque = crítico
        pifia = (tirada == 1) # Nat 1 = fallo automático con complicación
        total = tirada + mod

        # Nat 1: fallo automático sin importar modificadores
        if pifia:
            combate_msg(_narrar(
                f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                f"NAT 1. ¡PIFIA! El ataque falla estrepitosamente. "
                f"Narra una complicación: el arma se atasca, el jugador tropieza, "
                f"se golpea a sí mismo o queda expuesto."
            ))
        elif critico or total >= dc:# Si el ataque acierta, se calcula cuánto daño hace el jugador
            dado_daño = evaluacion.get("dado_daño")# Comprobamos si se puede hacer daño
            objetivo_id = evaluacion.get("objetivo")# Buscamos el id del objetivo en la escena, tanto enemigo como NPC

            if dado_daño: # Si se puede hacer daño
                if critico:
                    # Crítico: todos los dados al máximo + modificador (Cosmere RPG)
                    partes = dado_daño.lower().split("d")
                    cantidad = int(partes[0])
                    caras = int(partes[1])
                    daño = (cantidad * caras) + mod
                else:
                    daño = tirar_dado.invoke({"dado": dado_daño}) + mod
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

        vivos_actual = _get_vivos(entidades_presentes)
        if not vivos_actual:
            victoria_msg(_narrar(
                f"Todas las entidades han caído. El jugador triunfa en este enfrentamiento."
            ))
            return "victoria"

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

        if jugador["vida_actual"] <= 0:
            derrota_msg(_narrar(
                f"{jugador['nombre']} cae con {jugador['vida_actual']} HP. Narra su caída."
            ))
            return "derrota"

        _mostrar_estado(jugador, entidades_presentes)
