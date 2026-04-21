from langchain_core.tools import tool # Decorador que convierte la función en una tool para el LLM
from config import RESUMEN_PATH # Ruta al archivo donde guardamos el resumen de la partida


@tool
def mostrar_resumen() -> str:
    """Muestra el resumen actual de la partida."""
    if not RESUMEN_PATH.exists(): # Si todavía no hay resumen, devolvemos vacío
        return ""
    with open(RESUMEN_PATH, 'r', encoding='utf-8') as f: # Leemos el resumen completo del archivo
        return f.read() # Lo devolvemos tal cual para que el LLM lo use como contexto
