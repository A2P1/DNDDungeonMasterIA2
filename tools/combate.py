from langchain_core.tools import tool


@tool
def llamar_combate() -> str:
    """Úsala cuando el usuario quiera atacar, pelear o iniciar un enfrentamiento."""
    return "SEÑAL_INICIAR_COMBATE"
