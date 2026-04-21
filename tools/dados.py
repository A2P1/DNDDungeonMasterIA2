import random # Para generar números aleatorios al tirar los dados
from langchain_core.tools import tool # Decorador que convierte funciones en tools que el LLM puede usar


@tool
def tirar_dado(dado: str) -> int:
    """Tira un dado en formato NdX (ej: '1d6', '2d8'). Úsala para daño, curación, etc."""
    partes = dado.lower().split("d") # Separamos el string por la 'd', ej: '2d8' → ['2', '8']
    cantidad = int(partes[0]) # Cuántos dados tirar
    caras = int(partes[1]) # Cuántas caras tiene cada dado
    return sum(random.randint(1, caras) for _ in range(cantidad)) # Tiramos cada dado y sumamos los resultados


@tool
def tirar_d20() -> int:
    """Tira un d20. Úsala para tiradas de ataque, salvación o checks de habilidad."""
    return random.randint(1, 20) # Un número entre 1 y 20, ambos incluidos
