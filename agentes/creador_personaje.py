import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz del proyecto al path para que los imports funcionen

import json
from typing import Literal, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import STATS_PATH, MODEL_NAME, CREADOR_PERSONAJE_PROMPT_PATH


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


# ── LLM con structured output ───────────────────────────────────────────────
# .with_structured_output(PersonajeStats) hace que el LLM devuelva directamente
# una instancia de PersonajeStats validada, usando function calling por debajo.
_llm = ChatOpenAI(model=MODEL_NAME, temperature=0.3).with_structured_output(PersonajeStats)

with open(CREADOR_PERSONAJE_PROMPT_PATH, 'r', encoding='utf-8') as f: # Leemos el prompt desde el archivo de texto
    _PROMPT = f.read().strip()


MAX_REINTENTOS = 2


def _armas_fuera_de_catalogo(stats: dict, catalogo: list) -> list: # Devuelve los nombres de armas del personaje que no están en el catálogo
    if not catalogo: # Sin catálogo no hay nada que validar
        return []
    nombres_catalogo = {a["nombre"].lower() for a in catalogo} # Set de nombres normalizados para lookup case-insensitive
    faltantes = []
    arma_nombre = stats.get("arma", {}).get("nombre", "") # El arma equipada del personaje
    if arma_nombre and arma_nombre.lower() not in nombres_catalogo:
        faltantes.append(arma_nombre)
    for item in stats.get("inventario", []): # Cada arma del inventario también debe estar en el catálogo
        if item.get("tipo") == "arma":
            nombre = item.get("nombre", "")
            if nombre and nombre.lower() not in nombres_catalogo:
                faltantes.append(nombre)
    return faltantes


def crear_personaje(descripcion: str, campaña: dict = None) -> dict: # Genera la ficha del jugador a partir de su descripción y la guarda en stats.json
    contenido_human = f"Descripción del personaje: {descripcion}" # Empezamos construyendo el mensaje con la descripción del jugador

    if campaña and campaña.get("armas"): # Si la campaña tiene un catálogo de armas, se lo pasamos al LLM para que el personaje elija de ahí
        catalogo = json.dumps(campaña["armas"], ensure_ascii=False, indent=2)
        contenido_human += f"\n\nCatálogo de armas disponibles:\n{catalogo}"

    ultimo_error: Exception | None = None
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            personaje = _llm.invoke([ # Devuelve un PersonajeStats ya validado — no hay parseo manual
                SystemMessage(content=_PROMPT),
                HumanMessage(content=contenido_human)
            ])
            break
        except ValidationError as e: # Pydantic rechazó la respuesta (ej: atributo > 5, vida fuera de rango): reintentamos
            ultimo_error = e
            print(f"⚠️  Intento {intento}/{MAX_REINTENTOS} falló validación Pydantic ({e.error_count()} errores). Reintentando...")
    else:
        raise RuntimeError(
            "El LLM no consiguió generar una ficha que cumpliera el esquema tras varios intentos. "
            "Prueba a reformular la descripción del personaje."
        ) from ultimo_error

    stats = personaje.model_dump(by_alias=True, exclude_none=True) # Volcamos a dict usando los alias ("int" en vez de "int_"); exclude_none evita que los campos opcionales aparezcan como null
    stats["vida_actual"] = stats["vida_max"] # Nos aseguramos de que el personaje empieza con la vida al máximo

    if campaña and campaña.get("armas"): # Validación semántica post-hoc: aviso si el LLM eligió armas fuera del catálogo
        faltantes = _armas_fuera_de_catalogo(stats, campaña["armas"])
        if faltantes:
            print(f"⚠️  Armas del personaje fuera del catálogo de la campaña: {faltantes}. Se aceptan igualmente pero pueden ser inconsistentes.")

    STATS_PATH.parent.mkdir(parents=True, exist_ok=True) # Creamos la carpeta data/ si no existe
    with open(STATS_PATH, 'w', encoding='utf-8') as f: # Guardamos la ficha en stats.json
        json.dump(stats, f, indent=2, ensure_ascii=False)

    return stats


def personaje_existe() -> bool: # Comprueba si ya hay un personaje creado mirando si el archivo existe y no está vacío
    return STATS_PATH.exists() and STATS_PATH.stat().st_size > 0
