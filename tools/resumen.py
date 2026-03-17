from langchain_core.tools import tool
from config import RESUMEN_PATH

@tool
def mostrar_resumen() -> str:
    """Muestra el resumen actual de la partida."""
    if not RESUMEN_PATH.exists():
        return ""
    with open(RESUMEN_PATH, 'r', encoding='utf-8') as f:
        return f.read()