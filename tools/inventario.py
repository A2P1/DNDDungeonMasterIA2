import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import re
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import STATS_PATH, MODEL_NAME, TEMPERATURE_LOGICA
load_dotenv()
_llm = ChatOpenAI(model=MODEL_NAME, temperature=TEMPERATURE_LOGICA)


@tool
def get_inventario() -> str:
    """Devuelve el inventario completo del jugador en formato JSON.
    Útil cuando el jugador pregunta qué objetos o armas lleva encima."""
    if not STATS_PATH.exists():
        return "[]"
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        stats = json.load(f)
    return json.dumps(stats.get("inventario", []), ensure_ascii=False, indent=2)


def get_armas(jugador: dict) -> list:
    """Devuelve solo los items de tipo 'arma' del inventario del jugador."""
    return [item for item in jugador.get("inventario", []) if item.get("tipo") == "arma"]


def detectar_arma_en_accion(accion: str, armas: list) -> dict | None:
    """Detecta si el jugador menciona alguna de sus armas en la acción.

    Hace una búsqueda flexible (ej: 'espada' coincide con 'espada larga').

    Returns:
        El dict del arma si se menciona y existe en inventario, None si no se menciona.
    """
    if not armas:
        return None

    nombres = [a["nombre"] for a in armas]

    respuesta = _llm.invoke([
        SystemMessage(content=(
            "Eres un detector de armas en acciones de combate de rol. "
            "Dado el inventario de armas del jugador y su acción, determina si menciona alguna. "
            "Busca coincidencias flexibles: 'espada' coincide con 'espada larga', "
            "'el hacha' con 'hacha de guerra', 'mi daga' con 'daga', etc. "
            "Responde SOLO con JSON válido, sin texto extra:\n"
            '{"arma_mencionada": "<nombre exacto del inventario>" | null}'
        )),
        HumanMessage(content=f"Armas en inventario: {nombres}\nAcción del jugador: {accion}")
    ])

    try:
        contenido = respuesta.content
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', contenido)
        if match:
            contenido = match.group(1).strip()
        resultado = json.loads(contenido)
        nombre = resultado.get("arma_mencionada")
        if nombre:
            return next((a for a in armas if a["nombre"].lower() == nombre.lower()), None)
        return None
    except Exception:
        return None
