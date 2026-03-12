from langchain_core.tools import tool
from agentes.combate import combate
from tools.comprobar_enemigo import comprobar_enemigo
@tool
def llamar_combate() -> str:
    """Úsala cuando el usuario quiera atacar, pelear o iniciar un enfrentamiento."""
    enemigo = comprobar_enemigo.invoke({})
    if enemigo == True:
        combate()
    return "No hay enemigos"
    
