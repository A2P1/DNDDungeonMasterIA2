from langchain_core.tools import tool # Decorador que convierte la función en una tool para el LLM
from config import STATS_PATH # Ruta al archivo stats.json donde guardamos la ficha del jugador


@tool
def get_status() -> str:
    """Útil para cuando el usuario pregunte por sus estadísticas de salud (vida), defensa o ataque.
    Devuelve el estado actual del personaje en formato JSON."""
    if not STATS_PATH.exists(): # Si no hay ficha creada todavía, devolvemos un JSON vacío
        return "{}"
    with open(STATS_PATH, 'r', encoding='utf-8') as f: # Leemos la ficha del jugador del disco
        return f.read() # La devolvemos como string JSON para que el LLM la interprete
