import sys # Para manipular el path de Python
from pathlib import Path # Para manejar rutas de forma cómoda
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz al path para que los imports del proyecto funcionen

import json # Para leer y escribir el stats.json
import re # Para extraer dados de efectos (ej: "2d4" en pociones)
from typing import Optional
from dotenv import load_dotenv # Para cargar la API key desde el .env
from pydantic import BaseModel
from langchain_core.tools import tool # Decorador que convierte funciones en tools para el LLM
from langchain_openai import ChatOpenAI # El LLM que usamos para detectar armas en la acción
from langchain_core.messages import SystemMessage, HumanMessage # Tipos de mensaje para el LLM
from config import STATS_PATH, MODEL_NAME, TEMPERATURE_LOGICA # Ruta a stats.json y configuración del modelo

load_dotenv() # Cargamos la API key del .env


class DeteccionArma(BaseModel): # Esquema estructurado para la detección de armas en la acción
    arma_mencionada: Optional[str] = None # Nombre del arma que menciona el jugador, o null si no menciona ninguna
    en_inventario: bool # Si el arma mencionada coincide con alguna del inventario


_llm = ChatOpenAI(model=MODEL_NAME, temperature=TEMPERATURE_LOGICA).with_structured_output(DeteccionArma) # LLM con structured output: devuelve directamente un DeteccionArma validado


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


def get_armas(jugador: dict) -> list: # Filtra el inventario del jugador y devuelve solo las armas
    return [item for item in jugador.get("inventario", []) if item.get("tipo") == "arma"]


def verificar_arma_en_accion(accion: str, armas: list) -> dict: # Detecta si el jugador menciona un arma en su acción y comprueba si la tiene en el inventario
    """Detecta si el usuario menciona algún arma en su acción de ataque.
    Por ejemplo: "Le ataco con mi cuchillo" -- Detectar que el arma con la que quiere atacar es el cuchillo
    """
    if not armas: # Si el jugador no tiene armas, no puede mencionar ninguna
        return {"estado": "no_mencionada", "arma": None, "nombre": None}

    nombres = [a["nombre"] for a in armas] # Extraemos los nombres de las armas para pasárselos al LLM

    try:
        resultado = _llm.invoke([ # Devuelve un DeteccionArma ya validado gracias a structured output
            SystemMessage(content=(
                "Eres un detector de armas en acciones de combate de rol. "
                "Dado el inventario de armas del jugador y su acción, determina:\n"
                "1. ¿El jugador menciona usar algún arma específica? Si no, arma_mencionada debe ser null.\n"
                "2. Si menciona un arma, ¿está en el inventario? "
                "Busca coincidencias flexibles: 'espada' coincide con 'espada larga', "
                "'el hacha' con 'hacha de guerra', 'mi daga' con 'daga', etc.\n"
                "Si coincide, devuelve el nombre exacto del inventario. Si no coincide, devuelve el nombre tal cual lo dijo."
            )),
            HumanMessage(content=f"Armas en inventario: {nombres}\nAcción del jugador: {accion}")
        ])

        nombre = resultado.arma_mencionada # Nombre del arma mencionada (o None)

        if not nombre: # Si el LLM dice que no se menciona ningún arma, devolvemos no_mencionada
            return {"estado": "no_mencionada", "arma": None, "nombre": None}

        if resultado.en_inventario: # Si el arma está en el inventario, buscamos su ficha completa
            arma = next((a for a in armas if a["nombre"].lower() == nombre.lower()), None) # Buscamos el objeto arma por nombre
            if arma:
                return {"estado": "encontrada", "arma": arma, "nombre": nombre} # Devolvemos el arma encontrada

        return {"estado": "no_en_inventario", "arma": None, "nombre": nombre} # Si no está en el inventario, avisamos con el nombre que dijo
    except Exception:
        return {"estado": "no_mencionada", "arma": None, "nombre": None} # Si la llamada falla, asumimos que no se menciona arma
