from langchain_core.tools import tool
from config import STATS_PATH


@tool
def get_status() -> str:
    """Útil para cuando el usuario pregunte por sus estadísticas de salud (vida), defensa o ataque.
    Devuelve el estado actual del personaje en formato JSON."""
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return f.read()
