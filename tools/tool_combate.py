from langchain_core.tools import tool
from agentes.combate import combate

@tool
def llamar_combate() -> str:
    """Úsala cuando el usuario quiera atacar, pelear o iniciar un enfrentamiento."""
    combate()
    
