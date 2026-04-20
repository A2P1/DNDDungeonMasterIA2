import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz del proyecto al path para que los imports funcionen

import json
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import STATS_PATH, MODEL_NAME, CREADOR_PERSONAJE_PROMPT_PATH


load_dotenv() # Cargamos las variables de entorno para tener acceso a la API key

_llm = ChatOpenAI(model=MODEL_NAME, temperature=0.3) # Temperatura baja para que los stats generados sean coherentes y consistentes

with open(CREADOR_PERSONAJE_PROMPT_PATH, 'r', encoding='utf-8') as f: # Leemos el prompt desde el archivo de texto
    _PROMPT = f.read().strip()


def crear_personaje(descripcion: str, campaña: dict = None) -> dict: # Genera la ficha del jugador a partir de su descripción y la guarda en stats.json
    contenido_human = f"Descripción del personaje: {descripcion}" # Empezamos construyendo el mensaje con la descripción del jugador

    if campaña and campaña.get("armas"): # Si la campaña tiene un catálogo de armas, se lo pasamos al LLM para que el personaje elija de ahí
        catalogo = json.dumps(campaña["armas"], ensure_ascii=False, indent=2)
        contenido_human += f"\n\nCatálogo de armas disponibles:\n{catalogo}"

    respuesta = _llm.invoke([ # Llamamos al LLM con el prompt del sistema y el mensaje del jugador
        SystemMessage(content=_PROMPT),
        HumanMessage(content=contenido_human)
    ])

    contenido = respuesta.content
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', contenido) # Buscamos si el LLM ha envuelto el JSON en un bloque markdown
    if match:
        contenido = match.group(1).strip() # Si lo ha hecho, extraemos solo el JSON del interior
    stats = json.loads(contenido) # Parseamos el JSON a dict de Python

    stats["vida_actual"] = stats.get("vida_max", 12) # Nos aseguramos de que el personaje empieza con la vida al máximo

    STATS_PATH.parent.mkdir(parents=True, exist_ok=True) # Creamos la carpeta data/ si no existe
    with open(STATS_PATH, 'w', encoding='utf-8') as f: # Guardamos la ficha en stats.json
        json.dump(stats, f, indent=2, ensure_ascii=False)

    return stats


def personaje_existe() -> bool: # Comprueba si ya hay un personaje creado mirando si el archivo existe y no está vacío
    return STATS_PATH.exists() and STATS_PATH.stat().st_size > 0
