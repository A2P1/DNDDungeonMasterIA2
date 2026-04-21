import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz del proyecto al path para que los imports funcionen

import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from config import ENRIQUECEDOR_PROMPT_PATH, ENTIDADES_PATH, MODEL_NAME, TEMPERATURE_ENRIQUECEDOR

with open(ENRIQUECEDOR_PROMPT_PATH, 'r', encoding='utf-8') as f: # Leemos el prompt del enriquecedor desde el archivo de texto
    system_prompt = f.read().strip()

system_prompt_escaped = system_prompt.replace("{", "{{").replace("}", "}}") # Escapamos las llaves para que LangChain no las confunda con variables de plantilla

prompt = ChatPromptTemplate.from_messages([ # Plantilla con dos huecos: el catálogo de armas y las entidades a enriquecer
    ("system", system_prompt_escaped),
    ("human", "Catálogo de armas de la campaña:\n{catalogo_armas}\n\nEntidades a enriquecer:\n{entidades_raw}")
])

parser = JsonOutputParser() # Convierte la respuesta del LLM directamente a un dict de Python
llm = ChatOpenAI(model=MODEL_NAME, temperature=TEMPERATURE_ENRIQUECEDOR) # Temperatura baja para que las fichas generadas sean coherentes
chain_enriquecedor = prompt | llm | parser # Chain completa: rellenamos el prompt → LLM lo procesa → parseamos el JSON


def extraer_entidades_raw(campaña: dict) -> dict: # Recorre la campaña y extrae las plantillas básicas de enemigos y NPCs antes de enriquecerlas
    enemigos_raw = []
    npcs_raw = []

    for acto in campaña.get("actos", []): # Recorremos cada acto de la campaña
        for beat in acto.get("beats", []): # Y cada beat dentro del acto
            if beat.get("enemigos"): # Solo procesamos los beats que tengan enemigos definidos
                for enemigo in beat["enemigos"]: # Extraemos cada enemigo del beat con sus datos básicos
                    enemigos_raw.append({
                        "nombre": enemigo["nombre"],
                        "cantidad": enemigo.get("cantidad", 1), # Cuántos hay de ese tipo en el beat
                        "vida": enemigo.get("vida", 10),
                        "ac": enemigo.get("ac", 10),
                        "dado_daño": enemigo.get("dado_daño", "1d4"),
                        "xp": enemigo.get("xp", 25),
                        "beat_id": beat["id"], # Guardamos el beat al que pertenece para poder localizarlos después
                        "contexto": beat.get("descripcion", "") # Le pasamos el contexto del beat para que el LLM genere fichas coherentes con la historia
                    })

    for npc in campaña.get("npcs", []): # Extraemos también los NPCs de la lista principal de la campaña
        npcs_raw.append({
            "nombre": npc["nombre"],
            "rol": npc.get("rol", "neutral"), # aliado, neutral o enemigo
            "ubicacion": npc.get("ubicacion", ""),
            "beat_id": _encontrar_beat_npc(campaña, npc["nombre"]) # Buscamos en qué beat aparece este NPC
        })

    return {"enemigos_raw": enemigos_raw, "npcs_raw": npcs_raw}


def _encontrar_beat_npc(campaña: dict, nombre_npc: str) -> str: # Busca en qué beat aparece un NPC comparando su nombre con el campo "npc" de cada beat
    for acto in campaña.get("actos", []):
        for beat in acto.get("beats", []):
            if beat.get("npc", "").lower() == nombre_npc.lower(): # Comparamos en minúsculas para evitar problemas de capitalización
                return beat["id"]
    return "general" # Si no aparece en ningún beat concreto, lo marcamos como general


def enriquecer_entidades(campaña: dict) -> dict: # Toma las plantillas básicas, las manda al LLM para completarlas y guarda el resultado en entidades.json
    raw = extraer_entidades_raw(campaña) # Extraemos las plantillas básicas de la campaña
    raw_json = json.dumps(raw, indent=2, ensure_ascii=False) # Las convertimos a JSON para pasárselas al LLM
    catalogo = json.dumps(campaña.get("armas", []), indent=2, ensure_ascii=False) # También le pasamos el catálogo de armas para que asigne armas coherentes

    entidades = chain_enriquecedor.invoke({"entidades_raw": raw_json, "catalogo_armas": catalogo}) # El LLM genera las fichas completas

    ENTIDADES_PATH.parent.mkdir(parents=True, exist_ok=True) # Creamos la carpeta data/ si no existe
    with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f: # Guardamos las fichas generadas en entidades.json
        json.dump(entidades, f, indent=2, ensure_ascii=False)

    return entidades


def entidades_existen() -> bool: # Comprueba si ya hay fichas generadas mirando si el archivo existe
    return ENTIDADES_PATH.exists()


def cargar_entidades() -> dict: # Lee el entidades.json y lo devuelve como dict
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)
