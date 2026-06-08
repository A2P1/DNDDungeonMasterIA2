import sys # Para manipular el path de Python
from pathlib import Path # Para manejar rutas
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz al path para que los imports funcionen

import json # Para leer entidades.json y parsear respuestas del LLM
import re # Para extraer JSON de bloques markdown que devuelve el LLM
from langchain_openai import ChatOpenAI # El LLM que usamos para detectar intenciones y generar enemigos
from langchain_core.messages import SystemMessage, HumanMessage # Tipos de mensaje para el LLM
from langchain_core.output_parsers import JsonOutputParser # Para parsear las respuestas JSON del LLM detector
from config import ENTIDADES_PATH, MODEL_NAME, TEMPERATURE_LOGICA # Rutas y configuración del modelo
from tools.campana import get_siguiente_beat # Para saber qué beat está activo y filtrar entidades por beat_id

_llm_detector = ChatOpenAI(model=MODEL_NAME, temperature=TEMPERATURE_LOGICA) # LLM de temperatura 0 para decisiones lógicas
_parser_detector = JsonOutputParser() # Parser para las respuestas JSON del detector


def detectar_intento_ataque(user_input: str, resumen: str) -> bool: # Comprueba si el jugador quiere atacar a alguien presente en la escena
    respuesta = _llm_detector.invoke([ # Le preguntamos al LLM si hay intención de ataque y si hay objetivo en escena
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
        resultado = _parser_detector.parse(respuesta.content) # Parseamos la respuesta JSON
        return bool(resultado.get("quiere_atacar", False) and resultado.get("hay_objetivo_en_escena", False)) # True solo si quiere atacar Y hay objetivo
    except Exception:
        return False # Si falla el parseo, asumimos que no hay intento de ataque


def get_entidades_presentes() -> list: # Devuelve las entidades vivas (enemigos y NPCs) del beat activo registradas en entidades.json
    raw = get_siguiente_beat.invoke({}) # Consultamos cuál es el beat activo
    if raw == "CAMPAÑA COMPLETADA": # Si la campaña terminó, no hay entidades
        return []

    data = json.loads(raw) # Parseamos la respuesta del beat
    beat = data.get("beat", {}) # Extraemos el objeto beat
    beat_id = beat.get("id", "") # Guardamos el id del beat para filtrar entidades

    if not ENTIDADES_PATH.exists(): # Si no hay archivo de entidades todavía, devolvemos lista vacía
        return []

    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f: # Leemos todas las entidades generadas
        entidades = json.load(f)

    presentes = [] # Aquí iremos acumulando las entidades presentes en este beat

    for e in entidades.get("enemigos", []): # Filtramos los enemigos del beat actual que estén vivos
        if e.get("beat_origen") == beat_id and e.get("estado") == "vivo":
            e_copy = dict(e) # Hacemos una copia para no modificar el original
            e_copy["tipo_entidad"] = "enemigo" # Marcamos el tipo para el sistema de combate
            presentes.append(e_copy)

    npc_nombre = beat.get("npc") # Comprobamos si el beat tiene un NPC asociado
    if npc_nombre: # Si hay NPC, buscamos su ficha y comprobamos si está vivo
        for npc in entidades.get("npcs", []):
            if npc.get("nombre", "").lower() == npc_nombre.lower() and npc.get("estado") == "vivo":
                npc_copy = dict(npc) # Copia para no modificar el original
                npc_copy["tipo_entidad"] = "npc" # Marcamos el tipo como NPC
                presentes.append(npc_copy)

    return presentes # Devolvemos las entidades vivas del beat activo


def hay_entidad_atacable(user_input: str, resumen: str) -> bool: # Comprueba con el LLM si hay alguien presente a quien atacar según el contexto narrativo
    respuesta = _llm_detector.invoke([ # Le preguntamos si hay un objetivo razonable en la escena
        SystemMessage(content=(
            "Eres un árbitro de un juego de rol. "
            "Dado el resumen narrativo reciente y la acción del jugador, determina si "
            "hay alguna entidad (persona, criatura, monstruo) presente en la escena a la que "
            "el jugador pueda atacar razonablemente. "
            "No cuenten objetos inanimados como árboles, puertas o paredes. "
            "Responde SOLO con JSON válido, sin texto extra: "
            "{\"hay_objetivo\": true} o {\"hay_objetivo\": false}"
        )),
        HumanMessage(content=f"Resumen narrativo reciente:\n{resumen}\n\nAcción del jugador: {user_input}")
    ])
    try:
        contenido = respuesta.content # Guardamos el texto de la respuesta
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', contenido) # Por si el LLM envuelve el JSON en bloques markdown
        if match:
            contenido = match.group(1).strip() # Extraemos el JSON del bloque
        resultado = json.loads(contenido) # Parseamos el JSON
        return bool(resultado.get("hay_objetivo", False)) # True si hay objetivo atacable
    except Exception:
        return False # Si falla el parseo, asumimos que no hay objetivo


def generar_enemigo_narrativo(user_input: str, resumen: str) -> list: # Genera una ficha temporal para un enemigo narrativo y la inserta en entidades.json
    llm_gen = ChatOpenAI(model=MODEL_NAME, temperature=0.3) # Temperatura baja para stats coherentes
    respuesta = llm_gen.invoke([ # Pedimos al LLM que genere la ficha del enemigo basándose en el contexto
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
        contenido = respuesta.content # Guardamos el texto de la respuesta
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', contenido) # Por si el LLM envuelve el JSON en bloques markdown
        if match:
            contenido = match.group(1).strip() # Extraemos el JSON del bloque markdown

        enemigos = json.loads(contenido) # Parseamos la lista de enemigos generados
        if not isinstance(enemigos, list): # Si el LLM no devuelve una lista, algo fue mal
            return []

        with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f: # Leemos el archivo de entidades para insertar los nuevos
            entidades = json.load(f)

        ids_existentes = {e["id"] for e in entidades.get("enemigos", [])} # Set de ids ya registrados para evitar duplicados
        nombres_aliados = {n.get("nombre", "").lower() for n in entidades.get("npcs", []) if n.get("rol") == "aliado"}
        nuevos = [] # Aquí acumulamos los enemigos que sí vamos a insertar

        for e in enemigos: # Recorremos los enemigos generados por el LLM
            if e.get("id") and e["id"] not in ids_existentes and e.get("nombre", "").lower() not in nombres_aliados: # Solo insertamos si tiene id, no es duplicado y no es un aliado
                entidades["enemigos"].append(e) # Lo añadimos al archivo de entidades
                e_con_tipo = dict(e) # Copia para añadir tipo_entidad sin tocar el original
                e_con_tipo["tipo_entidad"] = "enemigo" # Marcamos como enemigo para el sistema de combate
                nuevos.append(e_con_tipo)

        with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f: # Guardamos entidades.json actualizado
            json.dump(entidades, f, indent=2, ensure_ascii=False)

        return nuevos # Devolvemos solo los enemigos recién insertados

    except Exception:
        return [] # Si algo falla, devolvemos lista vacía
