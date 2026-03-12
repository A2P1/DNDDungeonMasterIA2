import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from config import ENRIQUECEDOR_PROMPT_PATH, ENTIDADES_PATH, MODEL_NAME, TEMPERATURE_ENRIQUECEDOR

# Leer el prompt del enriquecedor
with open(ENRIQUECEDOR_PROMPT_PATH, 'r', encoding='utf-8') as f:
    system_prompt = f.read().strip()

# Prompt: recibe las entidades raw como JSON string
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "Entidades a enriquecer:\n{entidades_raw}")
])

parser = JsonOutputParser()
llm = ChatOpenAI(model=MODEL_NAME, temperature=TEMPERATURE_ENRIQUECEDOR)
chain_enriquecedor = prompt | llm | parser


def extraer_entidades_raw(campaña: dict) -> dict:
    """Extrae enemigos y NPCs de la campaña como plantillas sin enriquecer.

    Recorre todos los actos/beats buscando enemigos, y la lista de NPCs.
    Devuelve un dict con dos listas: enemigos_raw y npcs_raw.
    """
    enemigos_raw = []
    npcs_raw = []

    # Extraer enemigos de cada beat
    for acto in campaña.get("actos", []):
        for beat in acto.get("beats", []):
            if beat.get("enemigos"):
                for enemigo in beat["enemigos"]:
                    enemigos_raw.append({
                        "nombre": enemigo["nombre"],
                        "cantidad": enemigo.get("cantidad", 1),
                        "vida": enemigo.get("vida", 10),
                        "ac": enemigo.get("ac", 10),
                        "dado_daño": enemigo.get("dado_daño", "1d4"),
                        "xp": enemigo.get("xp", 25),
                        "beat_id": beat["id"],
                        "contexto": beat.get("descripcion", "")
                    })

    # Extraer NPCs
    for npc in campaña.get("npcs", []):
        npcs_raw.append({
            "nombre": npc["nombre"],
            "rol": npc.get("rol", "neutral"),
            "ubicacion": npc.get("ubicacion", ""),
            "beat_id": _encontrar_beat_npc(campaña, npc["nombre"])
        })

    return {"enemigos_raw": enemigos_raw, "npcs_raw": npcs_raw}


def _encontrar_beat_npc(campaña: dict, nombre_npc: str) -> str:
    """Busca en qué beat aparece un NPC por su nombre."""
    for acto in campaña.get("actos", []):
        for beat in acto.get("beats", []):
            if beat.get("npc", "").lower() == nombre_npc.lower():
                return beat["id"]
    return "general"


def enriquecer_entidades(campaña: dict) -> dict:
    """Extrae entidades de la campaña, las enriquece con el LLM y guarda en entidades.json.

    Args:
        campaña: El diccionario de la campaña generada por el director

    Returns:
        El diccionario con las entidades enriquecidas
    """
    raw = extraer_entidades_raw(campaña)
    raw_json = json.dumps(raw, indent=2, ensure_ascii=False)

    entidades = chain_enriquecedor.invoke({"entidades_raw": raw_json})

    with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f:
        json.dump(entidades, f, indent=2, ensure_ascii=False)

    return entidades


def entidades_existen() -> bool:
    """Comprueba si ya hay un archivo de entidades guardado."""
    return ENTIDADES_PATH.exists()


def cargar_entidades() -> dict:
    """Carga las entidades desde el JSON."""
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)
