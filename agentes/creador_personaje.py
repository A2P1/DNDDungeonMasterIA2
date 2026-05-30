import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz del proyecto al path para que los imports funcionen
import json
from typing import Literal, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from langchain_openai import ChatOpenAI
from openai import OpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import STATS_PATH, MODEL_NAME, CREADOR_PERSONAJE_PROMPT_PATH, IMAGEN_PATH
import base64
load_dotenv() # Cargamos las variables de entorno para tener acceso a la API key


# ── Esquema estructurado de la ficha del personaje ──────────────────────────
# Pydantic valida rangos y tipos. LangChain convierte estos modelos a JSON Schema
# y OpenAI está obligado a devolver una respuesta que encaje exactamente, así que
# no hace falta parsear markdown ni rezar para que el LLM devuelva JSON válido.

class Atributos(BaseModel):
    model_config = ConfigDict(populate_by_name=True) # Permite instanciar tanto con "int_" (nombre Python) como con "int" (alias JSON)
    fue: int = Field(ge=0, le=5)
    des: int = Field(ge=0, le=5)
    con: int = Field(ge=0, le=5)
    int_: int = Field(ge=0, le=5, alias="int") # "int" es palabra reservada en Python, usamos alias para el JSON
    sab: int = Field(ge=0, le=5)
    car: int = Field(ge=0, le=5)


class Arma(BaseModel):
    nombre: str
    dado_daño: str
    atributo: Literal["fue", "des", "int"]
    tipo: str


class ItemInventario(BaseModel): # Un item puede ser arma o consumible: los campos específicos son opcionales
    nombre: str
    tipo: Literal["arma", "consumible"]
    dado_daño: Optional[str] = None # solo para armas
    atributo: Optional[str] = None # solo para armas
    efecto: Optional[str] = None # solo para consumibles
    descripcion: Optional[str] = None


class PersonajeStats(BaseModel):
    nombre: str
    clase: str
    raza: str
    vida_max: int = Field(ge=10, le=20)
    ac: int = Field(ge=10, le=16)
    atributos: Atributos
    arma: Arma
    inventario: list[ItemInventario]


# ── LLM con structured output
# .with_structured_output(PersonajeStats) hace que el LLM devuelva directamente
# una instancia de PersonajeStats validada, usando function calling por debajo.
_llm = ChatOpenAI(model=MODEL_NAME, temperature=0.3).with_structured_output(PersonajeStats)

cliente = OpenAI() # Para generar imágenes
with open(CREADOR_PERSONAJE_PROMPT_PATH, 'r', encoding='utf-8') as f: # Leemos el prompt desde el archivo de texto
    _PROMPT = f.read().strip()

MAX_REINTENTOS = 2

def crear_personaje(descripcion: str, campaña: dict = None) -> dict: # Genera la ficha del jugador a partir de su descripción y la guarda en stats.json
    informacion = f"Descripción del personaje: {descripcion}"
    informacion += f"Contexto de la campaña: {json.dumps(campaña, ensure_ascii=False)}" if campaña else "No hay información adicional de la campaña."
    if campaña and campaña["armas"]:
        informacion += f"Catálogo de armas disponibles: {json.dumps(campaña['armas'], ensure_ascii=False)}"
    ultimoError = None
    for _ in range(MAX_REINTENTOS):
            try:
                stats = _llm.invoke([SystemMessage(content=_PROMPT), HumanMessage(content=informacion)]) # Lanzamos el LLM con el prompt y la información del personaje
                break
            except ValidationError as e:
                ultimoError = e
    else:
        raise RuntimeError(f"ERROR al cargar la campaña") from ultimoError
     
    stats_dict = stats.model_dump(by_alias=True)
    stats_dict["vida_actual"] = stats_dict["vida_max"]
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats_dict, f, indent=2, ensure_ascii=False)
    
    return stats_dict # Devolvemos la ficha como JSON, usando los alias para que el campo "int" se llame así en el JSON

def personaje_existe() -> bool: # Comprueba si ya hay un personaje creado mirando si el archivo existe y no está vacío
    return STATS_PATH.exists() and STATS_PATH.stat().st_size > 0

def crearimagenPersonaje(descripcion: str, campaña: dict = None) -> dict:
    informacion = f"Descripción del personaje: {descripcion}"
    informacion += f"Contexto de la campaña: {json.dumps(campaña, ensure_ascii=False)}" if campaña else "No hay información adicional de la campaña."
    if campaña and campaña["armas"]:
        informacion += f"Catálogo de armas disponibles: {json.dumps(campaña['armas'], ensure_ascii=False)}"
    ultimoError = None
    for _ in range(MAX_REINTENTOS):
            try:
                imagen = cliente.images.generate(model="gpt-image-1", prompt="Eres un generador de imágenes para la creación de un perfil del jugador. " \
                "Tu misión es generar una imagen del jugador con un estilo piexlart basándote en la descripción del personaje, la campaña en la que se desarrolla la trama y su catálogo de armas para que generes al personaje con un arma de su catálogo. " \
                "Tienes que representar al personaje en posición de ataque. Aquí está toda la información: " + informacion, size="1024x1024")
                break
            except Exception as e:
                ultimoError = e
    else:
        raise RuntimeError(f"ERROR al cargar la campaña") from ultimoError

    imagen_bytes = base64.b64decode(imagen.data[0].b64_json)
    with open(IMAGEN_PATH, 'wb') as f:
        f.write(imagen_bytes)
    return IMAGEN_PATH
