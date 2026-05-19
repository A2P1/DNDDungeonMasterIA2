import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz del proyecto al path para que los imports funcionen

import json
from typing import Literal, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from config import ENRIQUECEDOR_PROMPT_PATH, ENTIDADES_PATH, MODEL_NAME, TEMPERATURE_ENRIQUECEDOR

load_dotenv() # Cargamos las variables de entorno para tener acceso a la API key sin depender del orden de imports

with open(ENRIQUECEDOR_PROMPT_PATH, 'r', encoding='utf-8') as f: # Leemos el prompt del enriquecedor desde el archivo de texto
    system_prompt = f.read().strip()

system_prompt_escaped = system_prompt.replace("{", "{{").replace("}", "}}") # Escapamos las llaves para que LangChain no las confunda con variables de plantilla



# ── Esquema estructurado de entidades enriquecidas ──────────────────────────
# Sin structured output, un fallo de parseo aquí crasheaba la creación de la
# campaña después de haber pasado ya por el director. Ahora Pydantic valida
# rangos (atributos 0-5), enums (rol, disposición, tipo de loot) y tipos.

class AtributosEntidad(BaseModel):
    model_config = ConfigDict(populate_by_name=True) # "int" es palabra reservada: lo expones como alias JSON
    fue: int = Field(ge=0, le=5)
    des: int = Field(ge=0, le=5)
    con: int = Field(ge=0, le=5)
    int_: int = Field(ge=0, le=5, alias="int")
    sab: int = Field(ge=0, le=5)
    car: int = Field(ge=0, le=5)


class LootItem(BaseModel): # Los items de loot tienen forma distinta según tipo: los campos específicos son opcionales
    nombre: str
    tipo: Literal["arma", "consumible", "objeto"]
    dado_daño: Optional[str] = None # solo para armas
    efecto: Optional[str] = None # solo para consumibles
    descripcion: str


class Enemigo(BaseModel):
    id: str
    nombre: str
    beat_origen: str
    vida_max: int
    vida_actual: int
    ac: int
    xp: int
    atributos: AtributosEntidad
    arma: str
    dado_daño: str
    atributo_ataque: Literal["fue", "des", "int"]
    habilidades: list[str] = Field(default_factory=list)
    loot: list[LootItem] = Field(default_factory=list)
    estado: Literal["vivo", "muerto"] = "vivo"


class NPC(BaseModel):
    id: str
    nombre: str
    beat_origen: str
    vida_max: int
    vida_actual: int
    ac: int
    rol: Literal["aliado", "neutral", "traidor"]
    disposicion: Literal["amistoso", "indiferente"]
    estado: Literal["vivo", "muerto"] = "vivo"


class EntidadesEnriquecidas(BaseModel):
    enemigos: list[Enemigo]
    npcs: list[NPC]


llm = ChatOpenAI(model=MODEL_NAME, temperature=TEMPERATURE_ENRIQUECEDOR).with_structured_output(EntidadesEnriquecidas) # Temperatura baja + structured output fuerza el esquema exacto

def extraer_entidades_raw(campaña: dict) -> dict: # Recorre la campaña y extrae las plantillas básicas de enemigos y NPCs antes de enriquecerlas
    enemigo_bruto = []
    npc_bruto = []
    for actos in campaña.get("actos", []):
        for beats in actos.get("beats", []):
            for enemigo in beats.get("enemigos", []):
                enemigo_bruto.append ({
                    "nombre": enemigo["nombre"],
                    "cantidad": enemigo.get("cantidad", 1),
                    "vida": enemigo.get("vida", 10),
                    "ac": enemigo.get("ac", 12),
                    "dado_daño": enemigo.get("dado_daño", "1d8"),
                    "xp": enemigo.get("xp", 10),
                    "beat_id": beats.get("id", ""),
                    "contexto": beats.get("descripcion", "")
                })
    
    for npc in campaña.get("npcs", []):
        beat_npc = _encontrar_beat_npc(campaña, npc["nombre"])
        npc_bruto.append ({
            "nombre": npc["nombre"],
            "rol": npc.get("rol", ""),
            "sabe": npc.get("sabe", ""),
            "quiere": npc.get("quiere", ""),
            "ubicacion": npc.get("ubicacion", ""),
            "beat_id": beat_npc
        })
    return {"enemigos_raw": enemigo_bruto, "npcs_raw": npc_bruto}


def _encontrar_beat_npc(campaña: dict, nombre_npc: str) -> str: # Busca en qué beat aparece un NPC comparando su nombre con el campo "npc" de cada beat
    for acto in campaña.get("actos", []):
        for beats in acto.get("beats", []):
            if nombre_npc.lower() == beats.get("npc", "").lower():
                return beats.get("id", "")
            
    return "general"


MAX_REINTENTOS = 2


def _armas_fuera_de_catalogo(entidades: dict, catalogo: list) -> list: # Devuelve armas de enemigos y loot que no están en el catálogo de la campaña
    if not catalogo: # Sin catálogo no hay nada que validar
        return []
    nombres_catalogo = {a["nombre"].lower() for a in catalogo} # Set de nombres normalizados para lookup case-insensitive
    faltantes = []
    for enemigo in entidades.get("enemigos", []): # Recorremos cada enemigo
        arma = enemigo.get("arma", "")
        if arma and arma.lower() not in nombres_catalogo:
            faltantes.append(arma)
        for item in enemigo.get("loot", []): # Y las armas que sueltan como loot
            if item.get("tipo") == "arma":
                nombre = item.get("nombre", "")
                if nombre and nombre.lower() not in nombres_catalogo:
                    faltantes.append(nombre)
    return faltantes


def enriquecer_entidades(campaña: dict) -> dict: # Toma las plantillas básicas, las manda al LLM para completarlas y guarda el resultado en entidades.json

    info = f"Entidades a enriquecer: {json.dumps(extraer_entidades_raw(campaña))}"
    if campaña and campaña["armas"]:
        info += f"Catálogo de armas de la campaña: {json.dumps(campaña['armas'], ensure_ascii=False)}"

    ultimoerror = None
    for _ in range(MAX_REINTENTOS):
        try:
            entidad = llm.invoke([SystemMessage(content=system_prompt_escaped), HumanMessage(content=info)])
            break
        except ValidationError as e:
            ultimoerror = e
    else:
        raise RuntimeError("Error al enriquecer entidades") from ultimoerror
    
    entidades = entidad.model_dump(by_alias=True)
    with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f:
        json.dump(entidades, f, indent=2, ensure_ascii=False)
    return entidades

def entidades_existen() -> bool: # Comprueba si ya hay fichas generadas mirando si el archivo existe
    return ENTIDADES_PATH.exists()

def cargar_entidades() -> dict: # Lee el entidades.json y lo devuelve como dict
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)
