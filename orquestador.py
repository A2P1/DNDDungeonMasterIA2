from agentes.Narrador import narrador, narrador_inicio
from agentes.director import generar_campaña, campaña_existe, cargar_campaña
from agentes.enriquecedor import enriquecer_entidades, entidades_existen
from agentes.combate import combate
from agentes.combate_natural import combate_natural
from agentes.creador_personaje import crear_personaje, personaje_existe
from tools.campana import get_siguiente_beat, marcar_beat_completado
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from config import RESUMEN_PATH, CAMPAIGN_PATH, ENTIDADES_PATH, STATS_PATH, MODEL_NAME, TEMPERATURE_LOGICA
from ui import (narrador_msg, combate_msg, victoria_msg, derrota_msg,
                sistema_msg, titulo_msg, prompt_jugador, prompt_input)
import json

_llm_detector = ChatOpenAI(model=MODEL_NAME, temperature=TEMPERATURE_LOGICA)
_parser_detector = JsonOutputParser()


def _nueva_campaña():
    """Crea una campaña desde cero pidiendo datos al jugador."""
    titulo_msg("CREACIÓN DE CAMPAÑA")
    tema = prompt_input("¿Qué tipo de aventura quieres? (ej: mazmorra oscura, bosque maldito, ciudad pirata)")
    personaje = prompt_input("Describe tu personaje (ej: Thorin, enano guerrero)")

    sistema_msg("Generando tu campaña... (esto puede tardar unos segundos)")
    campaña = generar_campaña(tema, personaje)
    titulo_msg(f"¡Campaña '{campaña['titulo']}' creada!")
    narrador_msg(f"Gancho: {campaña['gancho']}")

    sistema_msg("Generando ficha de personaje...")
    stats = crear_personaje(personaje)
    sistema_msg(f"Personaje creado: {stats['nombre']} ({stats.get('raza', '')} {stats['clase']}) — HP: {stats['vida_max']} | AC: {stats['ac']} | Arma: {stats['arma']['nombre']}")

    return campaña


def _limpiar_partida():
    """Borra los archivos de la partida anterior para empezar de cero."""
    for path in [CAMPAIGN_PATH, ENTIDADES_PATH, STATS_PATH]:
        if path.exists():
            path.unlink()
    # Vaciar resumen (crear directorio si no existe)
    RESUMEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESUMEN_PATH, 'w', encoding='utf-8') as f:
        f.write("")


def iniciar_campaña():
    """Muestra menú de inicio: continuar partida existente o empezar nueva."""
    if campaña_existe():
        campaña = cargar_campaña()
        titulo_msg(f"Campaña encontrada: '{campaña.get('titulo', 'Sin título')}'")
        print("  1. Continuar partida")
        print("  2. Nueva campaña\n")
        opcion = prompt_input("Elige una opción (1/2)")

        if opcion == "2":
            _limpiar_partida()
            campaña = _nueva_campaña()
        else:
            sistema_msg("Continuando partida...")
            if not personaje_existe():
                sistema_msg("No se encontró ficha de personaje.")
                desc = prompt_input("Describe tu personaje para regenerar la ficha (ej: Thorin, enano guerrero)")
                stats = crear_personaje(desc)
                sistema_msg(f"Ficha regenerada: {stats['nombre']} ({stats.get('raza', '')} {stats['clase']})")
    else:
        campaña = _nueva_campaña()

    # Enriquecer entidades si no existen
    if not entidades_existen():
        sistema_msg("Generando fichas detalladas de enemigos y NPCs...")
        enriquecer_entidades(campaña)
        sistema_msg("Fichas generadas.")

    return campaña


def _beat_es_combate():
    """Comprueba si el siguiente beat pendiente es de combate. Devuelve el beat o None."""
    raw = get_siguiente_beat.invoke({})
    if raw == "CAMPAÑA COMPLETADA":
        return None
    data = json.loads(raw)
    beat = data.get("beat", {})
    if beat.get("tipo") in ("combate", "jefe", "climax"):
        return beat
    return None


def _detectar_intento_ataque(user_input: str, resumen: str) -> bool:
    """Detecta si el jugador quiere atacar a alguien que está presente en el contexto narrativo.
    Devuelve True solo si hay intención de ataque Y hay una entidad atacable en escena."""
    respuesta = _llm_detector.invoke([
        SystemMessage(content=(
            "Eres un árbitro de combate en un juego de rol. Tu tarea es determinar DOS cosas:\n"
            "1. ¿El jugador quiere atacar, golpear, herir o agredir físicamente a alguien?\n"
            "2. ¿El contexto narrativo reciente menciona algún personaje, criatura o entidad "
            "que pueda ser atacada (NPC, enemigo, guardia, animal, etc.)?\n\n"
            "Responde SOLO con JSON válido, sin texto extra:\n"
            "{\"quiere_atacar\": true/false, \"hay_objetivo_en_escena\": true/false}"
        )),
        HumanMessage(content=f"Contexto narrativo reciente:\n{resumen}\n\nAcción del jugador: {user_input}")
    ])
    try:
        resultado = _parser_detector.parse(respuesta.content)
        return bool(resultado.get("quiere_atacar", False) and resultado.get("hay_objetivo_en_escena", False))
    except Exception:
        return False


def _get_entidades_presentes() -> list:
    """Devuelve las entidades vivas (enemigos y NPCs) presentes en el beat actual."""
    raw = get_siguiente_beat.invoke({})
    if raw == "CAMPAÑA COMPLETADA":
        return []

    data = json.loads(raw)
    beat = data.get("beat", {})
    beat_id = beat.get("id", "")

    if not ENTIDADES_PATH.exists():
        return []

    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
        entidades = json.load(f)

    presentes = []

    # Enemigos del beat actual que estén vivos
    for e in entidades.get("enemigos", []):
        if e.get("beat_origen") == beat_id and e.get("estado") == "vivo":
            e_copy = dict(e)
            e_copy["tipo_entidad"] = "enemigo"
            presentes.append(e_copy)

    # NPC del beat (si tiene) que esté vivo
    npc_nombre = beat.get("npc")
    if npc_nombre:
        for npc in entidades.get("npcs", []):
            if npc.get("nombre", "").lower() == npc_nombre.lower() and npc.get("estado") == "vivo":
                npc_copy = dict(npc)
                npc_copy["tipo_entidad"] = "npc"
                presentes.append(npc_copy)

    return presentes


def _generar_enemigo_narrativo(user_input: str, resumen: str) -> list:
    """Genera stats temporales para un enemigo narrativo (no registrado en entidades.json)
    y lo inserta en entidades.json para que el sistema de combate pueda operar con él."""
    llm_gen = ChatOpenAI(model=MODEL_NAME, temperature=0.3)
    respuesta = llm_gen.invoke([
        SystemMessage(content=(
            "Eres un generador de stats de enemigos para D&D. "
            "Basándote en el contexto narrativo, genera stats para el o los enemigos "
            "que el jugador quiere atacar. "
            "Responde SOLO con JSON válido (lista), sin texto extra:\n"
            "[\n"
            "  {\n"
            '    "id": "temp_<nombre_sin_espacios>_1",\n'
            '    "nombre": "<nombre legible>",\n'
            '    "tipo": "humano",\n'
            '    "beat_origen": "temp",\n'
            '    "estado": "vivo",\n'
            '    "vida_max": <10-20>,\n'
            '    "vida_actual": <igual a vida_max>,\n'
            '    "ac": <10-13>,\n'
            '    "dado_daño": "1d6",\n'
            '    "xp": 50,\n'
            '    "atributos": {"fue": 2, "des": 2, "con": 1, "int": 1, "sab": 1, "car": 1},\n'
            '    "arma": "daga",\n'
            '    "descripcion": "<descripción breve>"\n'
            "  }\n"
            "]\n"
            "Genera solo los enemigos que el jugador menciona atacar directamente. "
            "Ajusta los stats al tipo de personaje que aparece en el contexto."
        )),
        HumanMessage(content=f"Contexto narrativo reciente:\n{resumen}\n\nAcción del jugador: {user_input}")
    ])
    try:
        # Extraer JSON aunque venga envuelto en bloques markdown ```json ... ```
        import re
        contenido = respuesta.content
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', contenido) #Extrae el contenido del JSON incluyendo saltos de línea, espacios y no espacios para leer el JSON 
        if match:
            contenido = match.group(1).strip()

        enemigos = json.loads(contenido)
        if not isinstance(enemigos, list):
            return []

        # Insertar en entidades.json para que dañar_enemigo pueda encontrarlos
        with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
            entidades = json.load(f)

        ids_existentes = {e["id"] for e in entidades.get("enemigos", [])}
        nuevos = []
        for e in enemigos:
            if e.get("id") and e["id"] not in ids_existentes:
                entidades["enemigos"].append(e)
                e_con_tipo = dict(e)
                e_con_tipo["tipo_entidad"] = "enemigo"
                nuevos.append(e_con_tipo)

        with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f:
            json.dump(entidades, f, indent=2, ensure_ascii=False)

        return nuevos
    except Exception as e:
        sistema_msg(f"[DEBUG] Excepción en _generar_enemigo_narrativo: {e}")
        return []


def main():
    load_dotenv()

    # Generar o cargar la campaña antes de empezar
    campaña = iniciar_campaña()

    while True:
        # Comprobar si el beat actual es de combate antes de pedir input
        beat_combate = _beat_es_combate()
        if beat_combate:
            # Transición narrativa: el narrador introduce el combate
            narrador_msg(narrador(f"[SISTEMA] El jugador llega al momento: {beat_combate['descripcion']}. Narra la aparición de los enemigos y la tensión del momento."))

            resultado = combate(beat_combate["id"])
            marcar_beat_completado.invoke({"beat_id": beat_combate["id"]})

            # Transición narrativa post-combate
            if resultado == "victoria":
                texto = narrador(f"[SISTEMA] El jugador ha ganado el combate en: {beat_combate['descripcion']}. Narra las consecuencias de la victoria y guía hacia lo que viene después.")
                victoria_msg(texto)
            else:
                texto = narrador(f"[SISTEMA] El jugador ha sido derrotado en: {beat_combate['descripcion']}. Narra su caída.")
                derrota_msg(texto)
                break
            continue

        resumen = RESUMEN_PATH.read_text(encoding='utf-8').strip() if RESUMEN_PATH.exists() else ""
        if resumen:
            user_input = prompt_jugador()
            if user_input.lower() == "salir":
                break

            # Detecta si el jugador quiere atacar fuera de un beat de combate
            if _detectar_intento_ataque(user_input, resumen): # Le pasamos la decisión del jugador y el resumen de la partida
                entidades = _get_entidades_presentes()
                if not entidades: 
                    entidades = _generar_enemigo_narrativo(user_input, resumen)
                if entidades:
                    resultado = combate_natural(entidades)

                    # Actualizar el resumen con lo que ocurrió en el combate
                    nombres_derrotados = ", ".join(e['nombre'] for e in entidades)
                    resumen_combate = (
                        f"El jugador inició un combate inesperado contra {nombres_derrotados} y "
                        f"{'venció, eliminándoles.' if resultado == 'victoria' else 'fue derrotado.'}"
                    )
                    RESUMEN_PATH.parent.mkdir(parents=True, exist_ok=True)
                    with open(RESUMEN_PATH, 'a', encoding='utf-8') as f:
                        f.write(resumen_combate + "\n")

                    if resultado == "derrota":
                        break

                    narrador_msg(narrador(
                        f"[SISTEMA] El jugador acaba de derrotar en combate a: {nombres_derrotados}. "
                        f"Esas criaturas/personajes han muerto y ya no están presentes. "
                        f"Narra las consecuencias de la victoria y continúa la historia."
                    ))
                    continue

            narrador_msg(narrador(user_input))
        else:
            narrador_msg(narrador_inicio(campaña))
main()
