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


def verificar_arma_en_accion(accion: str, armas: list) -> dict:
    """Detecta si el jugador menciona un arma en su acción y verifica si la tiene.

    Returns dict con:
      estado: "encontrada" | "no_en_inventario" | "no_mencionada"
      arma:   dict del arma si encontrada, None en otro caso
      nombre: nombre que dijo el jugador, None si no mencionó ninguna
    """
    if not armas:
        return {"estado": "no_mencionada", "arma": None, "nombre": None}

    nombres = [a["nombre"] for a in armas]

    respuesta = _llm.invoke([
        SystemMessage(content=(
            "Eres un detector de armas en acciones de combate de rol. "
            "Dado el inventario de armas del jugador y su acción, determina:\n"
            "1. ¿El jugador menciona usar algún arma específica?\n"
            "2. Si menciona un arma, ¿está en el inventario? "
            "Busca coincidencias flexibles: 'espada' coincide con 'espada larga', "
            "'el hacha' con 'hacha de guerra', 'mi daga' con 'daga', etc.\n"
            "Responde SOLO con JSON válido, sin texto extra:\n"
            '{"arma_mencionada": "<nombre exacto del inventario si coincide, '
            'o el nombre que dijo el jugador si no coincide, o null si no menciona ninguna>", '
            '"en_inventario": true | false}'
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
        en_inventario = resultado.get("en_inventario", False)

        if not nombre:
            return {"estado": "no_mencionada", "arma": None, "nombre": None}

        if en_inventario:
            arma = next((a for a in armas if a["nombre"].lower() == nombre.lower()), None)
            if arma:
                return {"estado": "encontrada", "arma": arma, "nombre": nombre}

        return {"estado": "no_en_inventario", "arma": None, "nombre": nombre}
    except Exception:
        return {"estado": "no_mencionada", "arma": None, "nombre": None}
