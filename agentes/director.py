import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz del proyecto al path para que los imports funcionen

import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException
from openai import OpenAI
from config import DIRECTOR_PROMPT_PATH, CAMPAIGN_PATH, MODEL_NAME, IMAGEN1_PATH
import base64

load_dotenv() # Cargamos las variables de entorno para tener acceso a la API key sin depender del orden de imports

with open(DIRECTOR_PROMPT_PATH, 'r', encoding='utf-8') as f: # Leemos el prompt del director desde el archivo de texto
    system_prompt = f.read().strip()

system_prompt_escaped = system_prompt.replace("{", "{{").replace("}", "}}") # Escapamos las llaves para que LangChain no las confunda con variables de plantilla

prompt = ChatPromptTemplate.from_messages([ # Plantilla del prompt con dos huecos: tema y personaje
    ("system", system_prompt_escaped),
    ("human", "Tema: {tema}. Personaje: {personaje}")
])

parser = JsonOutputParser() # Convierte la respuesta del LLM directamente a un dict de Python
cliente = OpenAI() # Para generar imágenes
llm = ChatOpenAI(model=MODEL_NAME, temperature=0.9) # Temperatura alta para que la campaña generada sea creativa y variada
chain_director = prompt | llm | parser # Chain completa: rellenamos el prompt → LLM lo procesa → parseamos el JSON


MAX_REINTENTOS = 2


def generar_campaña(tema: str, personaje: str) -> dict: # Genera la campaña completa y la guarda en campaign.json
    ultimo_error: Exception | None = None
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            campaña = chain_director.invoke({ # Ejecutamos la chain con el tema y el personaje del jugador
                "tema": tema,
                "personaje": personaje
            })
            break
        except OutputParserException as e: # El LLM devolvió texto en vez de JSON (rechazos espurios, prosa extra): reintentamos
            ultimo_error = e
            print(f"Intento {intento}/{MAX_REINTENTOS} falló al parsear JSON. Reintentando...")
    else:
        raise RuntimeError(
            "El LLM no devolvió un JSON válido tras varios intentos. "
            "Prueba a reformular el tema o el personaje."
        ) from ultimo_error

    CAMPAIGN_PATH.parent.mkdir(parents=True, exist_ok=True) # Creamos la carpeta data/ si no existe
    with open(CAMPAIGN_PATH, 'w', encoding='utf-8') as f: # Guardamos la campaña generada en campaign.json
        json.dump(campaña, f, indent=2, ensure_ascii=False)

    return campaña


def campaña_existe() -> bool: # Comprueba si ya hay una campaña guardada mirando si el archivo existe
    return CAMPAIGN_PATH.exists()


def cargar_campaña() -> dict: # Lee el campaign.json y lo devuelve como dict
    with open(CAMPAIGN_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def crearimagenMundo(tema: str) -> dict:
    informacion = f"Tema de la campaña: {json.dumps(tema, ensure_ascii=False)}" if tema else "No hay información adicional de la campaña."
    for _ in range(MAX_REINTENTOS):
            try:
                imagen = cliente.images.generate(model="gpt-image-1", prompt="Eres un generador de imágenes para la creación de una ilustración de un mundo. " \
                "Tu misión es generar una imagen del mundo en general con un estilo piexlart con una vista isométrica basándote en el tema escogido por el usuario. " \
                "Aquí está toda la información: " + informacion, size="1024x1024")
                break
            except Exception as e:
                ultimoError = e
    else:
        raise RuntimeError(f"ERROR al cargar la campaña") from ultimoError

    imagen_bytes = base64.b64decode(imagen.data[0].b64_json)
    with open(IMAGEN1_PATH, 'wb') as f:
        f.write(imagen_bytes)
    return IMAGEN1_PATH
