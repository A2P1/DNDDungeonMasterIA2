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


@tool
def add_item_to_inventory(item_json: str) -> str:
    """Añade un item al inventario del jugador. Recibe un JSON string con el item.
    Estructura del item: {"nombre": "...", "tipo": "arma|consumible|objeto", "dado_daño": "..." (si arma), "efecto": "..." (si consumible), "descripcion": "..."}.
    Útil para loot de enemigos, recompensas de NPCs o items encontrados en el mundo."""
    if not STATS_PATH.exists():
        return "Error: no hay ficha de jugador"
    try:
        item = json.loads(item_json) if isinstance(item_json, str) else item_json
    except (json.JSONDecodeError, TypeError):
        return "Error: JSON del item no válido"

    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        stats = json.load(f)

    if "inventario" not in stats:
        stats["inventario"] = []

    stats["inventario"].append(item)

    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    return f"'{item['nombre']}' añadido al inventario."


@tool
def usar_item(nombre_item: str) -> str:
    """Usa un item consumible del inventario (ej: poción de cura).
    Lo elimina del inventario y devuelve su efecto para que el narrador lo aplique.
    Si el item recupera HP, se aplica automáticamente."""
    if not STATS_PATH.exists():
        return "Error: no hay ficha de jugador"

    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        stats = json.load(f)

    inventario = stats.get("inventario", [])
    item_idx = None
    for i, item in enumerate(inventario):
        if item["nombre"].lower() == nombre_item.lower() and item.get("tipo") == "consumible":
            item_idx = i
            break

    if item_idx is None:
        return f"No tienes '{nombre_item}' en el inventario o no es un item consumible."

    item = inventario.pop(item_idx)
    efecto = item.get("efecto", "sin efecto conocido")

    # Si el efecto menciona recuperar HP, tiramos el dado y lo aplicamos
    hp_recuperado = 0
    if "HP" in efecto.upper() or "hp" in efecto.lower():
        import re as _re
        match = _re.search(r'(\d+)d(\d+)', efecto)
        if match:
            from tools.dados import tirar_dado
            hp_recuperado = tirar_dado.invoke({"dado": match.group(0)})
            stats["vida_actual"] = min(
                stats.get("vida_max", stats["vida_actual"]),
                stats["vida_actual"] + hp_recuperado
            )

    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    if hp_recuperado > 0:
        return (f"Usas '{item['nombre']}'. Recuperas {hp_recuperado} HP. "
                f"Vida: {stats['vida_actual']}/{stats['vida_max']}")
    return f"Usas '{item['nombre']}'. Efecto: {efecto}"


def get_armas(jugador: dict) -> list:
    """Devuelve las armas que tiene el jugador en su inventario"""
    return [item for item in jugador.get("inventario", []) if item.get("tipo") == "arma"]


def verificar_arma_en_accion(accion: str, armas: list) -> dict:
    """Detecta si el usuario menciona algún arma en su acción de ataque.
    Por ejemplo: "Le ataco con mi cuchillo" -- Detectar que el arma con la que quiere atacar es el cuchillo

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
