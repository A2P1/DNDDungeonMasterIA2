import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from config import DIRECTOR_PROMPT_PATH, CAMPAIGN_PATH, MODEL_NAME

# Leer el prompt del director
with open(DIRECTOR_PROMPT_PATH, 'r', encoding='utf-8') as f:
    system_prompt = f.read().strip()

# Prompt con variables para tema y personaje
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "Tema: {tema}. Personaje: {personaje}")
])

# Parser que convierte la respuesta del LLM en un dict de Python
parser = JsonOutputParser()

# La chain completa: prompt → LLM → parser
llm = ChatOpenAI(model=MODEL_NAME, temperature=0.9)
chain_director = prompt | llm | parser


def generar_campaña(tema: str, personaje: str) -> dict:
    """Genera una campaña completa y la guarda en campaign.json.

    Args:
        tema: Temática deseada (ej: "mazmorra oscura con no-muertos")
        personaje: Descripción del personaje (ej: "Thorin, enano guerrero")

    Returns:
        El diccionario con la campaña generada
    """
    campaña = chain_director.invoke({
        "tema": tema,
        "personaje": personaje
    })

    with open(CAMPAIGN_PATH, 'w', encoding='utf-8') as f:
        json.dump(campaña, f, indent=2, ensure_ascii=False)

    return campaña


def campaña_existe() -> bool:
    """Comprueba si ya hay una campaña guardada."""
    return CAMPAIGN_PATH.exists()


def cargar_campaña() -> dict:
    """Carga la campaña desde el JSON."""
    with open(CAMPAIGN_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)
