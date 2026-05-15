import random # Para generar números aleatorios al tirar los dados
from langchain_core.tools import tool # Decorador que convierte funciones en tools que el LLM puede usar


@tool
def tirar_dado(dado: str) -> int:
    """Tira un dado en formato NdX (ej: '1d6', '2d8'). Úsala para daño, curación, etc."""
    try:

        cantidad, tipo = dado.lower().split('d')
        numero = 0
        for _ in range(int(cantidad)):
            numero += random.randint(1, int(tipo)) # Un número entre 1 y el tipo del dado, ambos incluidos
        return numero
    except Exception as e:
        raise ValueError(f"Dado inválido: '{dado}'. El formato correcto es NdX, por ejemplo '1d6' o '2d8'. Error original: {e}")
@tool
def tirar_d20() -> int:
    """Tira un d20. Úsala para tiradas de ataque, salvación o checks de habilidad."""
    return random.randint(1, 20) # Un número entre 1 y 20, ambos incluidos
