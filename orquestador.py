from agentes.HolaMundoLangchain import narrador, narrador_inicio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from agentes.combate import combate
from tools.stats import get_status
from tools.combate import llamar_combate
from config import STATS_PATH, RESUMEN_PATH
import json



def main():
    load_dotenv()
    llm = ChatOpenAI(model="gpt-4o", temperature=0.9)
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        datos = json.load(f)
    messages = [
        
    ]
    EnCombate = 0
    llm_tools = llm.bind_tools([get_status, llamar_combate])
    Herramientas = [get_status, llamar_combate]
    mapa_herramientas = {t.name: t for t in Herramientas}


    while True:
        with open(RESUMEN_PATH, 'r', encoding='utf-8') as f:
            resumen = f.read().strip() # Cargamos el resumen de la partida para pasársela al narrador
        if resumen:
            
            user_input = input("Escribe tu mensaje (o 'salir' para terminar): \n")
            respuesta = llm_tools.invoke(user_input) 

            if respuesta.tool_calls:
                    for tool_call in respuesta.tool_calls:
                        # Buscamos la función en nuestro mapa y la ejecutamos
                        seleccionada = mapa_herramientas[tool_call["name"]]
                        respuesta_herramienta = seleccionada.invoke(tool_call["args"])
                        # Si de todas las herramientas llama al combate
                        if tool_call["name"] == "llamar_combate":
                            #resultado_validacion = llamar_combate.invoke({"resumen_actual": resumen})
                            #if "COMBATE PERMITIDO" in resultado_validacion:
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
                        '''else:
                            respuesta_herramienta = resultado_validacion'''
                        # DE AQUÍ

                        # 3. Le pasamos el resultado a la IA para que lo procese
                        # Es vital pasarle el ID para que la IA sepa a qué petición responde
                        mensaje_herramienta = ToolMessage(
                            content=str(respuesta_herramienta), 
                            tool_call_id=tool_call["id"]
                        )
                        # 4. Invocación final: La IA ahora sí tiene los datos para hablar
                        respuesta_final = llm_tools.invoke([
                            HumanMessage(content=user_input),
                            respuesta, # La petición original
                            mensaje_herramienta # La respuesta de la función
                        ])
                        
                        print(respuesta_final.content)
                        # HASTA AQUÍ ES FIJO PARA TODAS LAS TOOLS

            else:
                if user_input.lower() == "salir":
                    break
                    ''' else:
                    messages.append(HumanMessage(content=user_input)) # Guardamos la info que ha introducido el usuario para procesarla
                    decision = llm_tools.invoke([
                        SystemMessage(content=f"Si el usuario menciona alguna de estas palabras: combate, lucha, pelea, ataco, ataque o enfrento, guarda la palabra 'COMBATE' en la variable decision" ),
                        HumanMessage(content=user_input)
                    ]).content # Comprobamos si el usuario quiere entrar en combate
                    if llamar_combate() == 1:
                        EnCombate = 1
                        print('Combate iniciado')
                        # EL BUCLE WHILE METERLO EN UNA FUNCIÓN APARTE PARA MEJOR COORDINACIÓN
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

                '''
                else:
                    print(narrador(resumen, user_input)) # Hacemos la llamada al narrador pasándole el resumen y la información introducida por el usuario
        else:
            print(narrador_inicio())
main()

