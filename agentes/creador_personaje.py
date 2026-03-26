import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from config import STATS_PATH, MODEL_NAME, CREADOR_PERSONAJE_PROMPT_PATH


load_dotenv()

_llm = ChatOpenAI(model=MODEL_NAME, temperature=0.3)
_parser = JsonOutputParser()
with open(CREADOR_PERSONAJE_PROMPT_PATH, 'r', encoding='utf-8') as f:
        system_prompt = f.read().strip()
_PROMPT = system_prompt


def crear_personaje(descripcion: str) -> dict:
    """Genera la ficha de stats del jugador a partir de su descripción libre.

    Guarda el resultado en data/stats.json y lo devuelve como dict.
    """
    respuesta = _llm.invoke([
        SystemMessage(content=_PROMPT),
        HumanMessage(content=f"Descripción del personaje: {descripcion}")
    ])

    import re
    contenido = respuesta.content
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', contenido)
    if match:
        contenido = match.group(1).strip()
    stats = json.loads(contenido)

    # Asegurar que vida_actual == vida_max al crear
    stats["vida_actual"] = stats.get("vida_max", 12)

    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    return stats


def personaje_existe() -> bool:
    return STATS_PATH.exists() and STATS_PATH.stat().st_size > 0
