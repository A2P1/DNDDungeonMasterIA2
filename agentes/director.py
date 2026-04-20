import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz del proyecto al path para que los imports funcionen

import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from config import DIRECTOR_PROMPT_PATH, CAMPAIGN_PATH, MODEL_NAME

with open(DIRECTOR_PROMPT_PATH, 'r', encoding='utf-8') as f: # Leemos el prompt del director desde el archivo de texto
    system_prompt = f.read().strip()

system_prompt_escaped = system_prompt.replace("{", "{{").replace("}", "}}") # Escapamos las llaves para que LangChain no las confunda con variables de plantilla

prompt = ChatPromptTemplate.from_messages([ # Plantilla del prompt con dos huecos: tema y personaje
    ("system", system_prompt_escaped),
    ("human", "Tema: {tema}. Personaje: {personaje}")
])

parser = JsonOutputParser() # Convierte la respuesta del LLM directamente a un dict de Python

llm = ChatOpenAI(model=MODEL_NAME, temperature=0.9) # Temperatura alta para que la campaña generada sea creativa y variada
chain_director = prompt | llm | parser # Chain completa: rellenamos el prompt → LLM lo procesa → parseamos el JSON


def generar_campaña(tema: str, personaje: str) -> dict: # Genera la campaña completa y la guarda en campaign.json
    campaña = chain_director.invoke({ # Ejecutamos la chain con el tema y el personaje del jugador
        "tema": tema,
        "personaje": personaje
    })

    CAMPAIGN_PATH.parent.mkdir(parents=True, exist_ok=True) # Creamos la carpeta data/ si no existe
    with open(CAMPAIGN_PATH, 'w', encoding='utf-8') as f: # Guardamos la campaña generada en campaign.json
        json.dump(campaña, f, indent=2, ensure_ascii=False)

    return campaña


def campaña_existe() -> bool: # Comprueba si ya hay una campaña guardada mirando si el archivo existe
    return CAMPAIGN_PATH.exists()


def cargar_campaña() -> dict: # Lee el campaign.json y lo devuelve como dict
    with open(CAMPAIGN_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)
