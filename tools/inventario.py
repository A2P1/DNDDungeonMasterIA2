import sys # Para manipular el path de Python
from pathlib import Path # Para manejar rutas de forma cómoda
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz al path para que los imports del proyecto funcionen

import json # Para leer y escribir el stats.json
import re # Para extraer dados de efectos (ej: "2d4" en pociones)
from dotenv import load_dotenv # Para cargar la API key desde el .env
from langchain_core.tools import tool # Decorador que convierte funciones en tools para el LLM
from config import STATS_PATH # Ruta a stats.json

load_dotenv() # Cargamos la API key del .env


@tool
def get_inventario() -> str:
    """Devuelve el inventario completo del jugador en formato JSON.
    Útil cuando el jugador pregunta qué objetos o armas lleva encima."""
    if not STATS_PATH.exists(): # Si no hay ficha de jugador, devolvemos lista vacía
        return "[]"
    with open(STATS_PATH, 'r', encoding='utf-8') as f: # Leemos la ficha del jugador
        stats = json.load(f)
    return json.dumps(stats.get("inventario", []), ensure_ascii=False, indent=2) # Devolvemos solo el inventario


@tool
def add_item_to_inventory(item_json: str) -> str:
    """Añade un item al inventario del jugador. Recibe un JSON string con el item.
    Estructura del item: {"nombre": "...", "tipo": "arma|consumible|objeto", "dado_daño": "..." (si arma), "efecto": "..." (si consumible), "descripcion": "..."}.
    Útil para loot de enemigos, recompensas de NPCs o items encontrados en el mundo."""
    if not STATS_PATH.exists(): # Si no hay ficha, no podemos añadir nada
        return "Error: no hay ficha de jugador"

    try:
        item = json.loads(item_json) if isinstance(item_json, str) else item_json # Parseamos el item, tanto si viene como string como si ya es dict
    except (json.JSONDecodeError, TypeError):
        return "Error: JSON del item no válido" # Si el JSON está mal formado, avisamos

    with open(STATS_PATH, 'r', encoding='utf-8') as f: # Leemos la ficha actual del jugador
        stats = json.load(f)

    if "inventario" not in stats: # Si el jugador no tiene inventario todavía, lo creamos
        stats["inventario"] = []

    stats["inventario"].append(item) # Añadimos el nuevo item al inventario

    with open(STATS_PATH, 'w', encoding='utf-8') as f: # Guardamos la ficha actualizada en el disco
        json.dump(stats, f, indent=2, ensure_ascii=False)

    return f"'{item['nombre']}' añadido al inventario." # Confirmamos que se ha añadido


@tool
def usar_item(nombre_item: str) -> str:
    """Usa un item consumible del inventario (ej: poción de cura).
    Lo elimina del inventario y devuelve su efecto para que el narrador lo aplique.
    Si el item recupera HP, se aplica automáticamente."""
    if not STATS_PATH.exists(): # Si no hay ficha, no hay inventario
        return "Error: no hay ficha de jugador"

    with open(STATS_PATH, 'r', encoding='utf-8') as f: # Leemos la ficha del jugador
        stats = json.load(f)

    inventario = stats.get("inventario", []) # Sacamos el inventario
    item_idx = None # Índice del item que queremos usar
    for i, item in enumerate(inventario): # Buscamos el item por nombre entre los consumibles
        if item["nombre"].lower() == nombre_item.lower() and item.get("tipo") == "consumible":
            item_idx = i # Guardamos el índice para borrarlo después
            break

    if item_idx is None: # Si no encontramos el item o no es consumible, avisamos
        return f"No tienes '{nombre_item}' en el inventario o no es un item consumible."

    item = inventario.pop(item_idx) # Sacamos el item del inventario (se consume al usarlo)
    efecto = item.get("efecto", "sin efecto conocido") # Leemos el efecto del item

    hp_recuperado = 0 # Inicializamos el HP recuperado a 0
    if "HP" in efecto.upper() or "hp" in efecto.lower(): # Si el efecto menciona HP, tiramos el dado de curación
        match = re.search(r'(\d+)d(\d+)', efecto) # Buscamos el dado de curación en el texto del efecto
        if match:
            from tools.dados import tirar_dado # Import local para evitar importaciones circulares
            hp_recuperado = tirar_dado.invoke({"dado": match.group(0)}) # Tiramos el dado y guardamos el resultado
            stats["vida_actual"] = min( # Sumamos el HP recuperado sin superar el máximo
                stats.get("vida_max", stats["vida_actual"]),
                stats["vida_actual"] + hp_recuperado
            )

    with open(STATS_PATH, 'w', encoding='utf-8') as f: # Guardamos la ficha actualizada (sin el item y con el HP nuevo)
        json.dump(stats, f, indent=2, ensure_ascii=False)

    if hp_recuperado > 0: # Si se recuperó HP, lo mostramos en el mensaje
        return (f"Usas '{item['nombre']}'. Recuperas {hp_recuperado} HP. "
                f"Vida: {stats['vida_actual']}/{stats['vida_max']}")
    return f"Usas '{item['nombre']}'. Efecto: {efecto}" # Si no recupera HP, solo mostramos el efecto
