import random
from langchain_core.tools import tool


@tool
def tirar_dado(dado: str) -> int:
    """Tira un dado en formato NdX (ej: '1d6', '2d8'). Úsala para daño, curación, etc."""
    partes = dado.lower().split("d")
    cantidad = int(partes[0])
    caras = int(partes[1])
    return sum(random.randint(1, caras) for _ in range(cantidad))

@tool
def tirar_d20() -> int:
    """Tira un d20. Úsala para tiradas de ataque, salvación o checks de habilidad."""
    return random.randint(1, 20)

