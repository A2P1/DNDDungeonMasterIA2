from langchain_core.tools import tool


@tool
def llamar_combate() -> str:
    """Úsala cuando el usuario quiera atacar, pelear o iniciar un enfrentamiento."""
    EnCombate = 1 # Asignamos el flag EnCombate a 1
    print("\n--- ¡ESPADAS FUERA! EL COMBATE COMIENZA ---\n")
    while EnCombate == 1:
        accion = input("Qué acción quieres realizar? (atacar o huir)")
        resultado, valor = combate(accion, datos)
        #messages.append(HumanMessage(content=combate(accion))) # Guardamos la información del combate para que el narrador pueda procesarla y generar un resumen coherente
        finalizado = llm_tools.invoke([
            SystemMessage(content=f"Si el combate ha terminado, guarda la palabra 'FINALIZADO' en la variable finalizado"),
            HumanMessage(content=resultado)
        ]).content
        if "FINALIZADO" in finalizado.upper():
            comentario = llm_tools.invoke([
            SystemMessage(content=f"el jugador ha sacado un {valor} al tirar los dados en un D&D. Si es mayor a 12 ha acertado, si no, ha fracasado. Narra esto de forma genérica en 1 frase mostrando el valor del dado teniendo en cuenta este resultado: {resultado} y guardalo en la variable 'comentario'")
        ])
        print(comentario.content)
    EnCombate = 0
    return "SEÑAL_INICIAR_COMBATE"
