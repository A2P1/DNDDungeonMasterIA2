from agentes.HolaMundoLangchain import narrador, narrador_inicio # Importamos la función narrador del archivo HolaMundoLangchain.py para poder utilizarla en el orquestador
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from agentes.combate import combate
import json

# Funciona como un orquestador lógico programado por mí para que siempre llame al narrador
def main():
    load_dotenv()
    llm = ChatOpenAI(model="gpt-4o", temperature=0.9)
    with open('stats.json', 'r', encoding= 'utf-8') as f:
        datos = json.load(f)
    messages = [
        
    ]
    EnCombate = 0
    

    while True:
        with open('resumen.txt', 'r', encoding='utf-8') as f:
            resumen = f.read().strip() # Cargamos el resumen de la partida para pasársela al narrador
        if resumen:
            user_input = input("Escribe tu mensaje (o 'salir' para terminar): ")
            if user_input.lower() == "salir":
                break
            else:
                messages.append(HumanMessage(content=user_input)) # Guardamos la info que ha introducido el usuario para procesarla
                decision = llm.invoke([
                    SystemMessage(content=f"Si el usuario menciona alguna de estas palabras: combate, lucha, pelea, ataco, ataque o enfrento, guarda la palabra 'COMBATE' en la variable decision" ),
                    HumanMessage(content=user_input)
                ]).content # Comprobamos si el usuario quiere entrar en combate
                if "COMBATE" in decision.upper():
                    EnCombate = 1
                    print('Combate iniciado')

                    while EnCombate == 1:
                        accion = input("Qué acción quieres realizar? (atacar o huir)")
                        resultado, valor = combate(accion, datos)
                        #messages.append(HumanMessage(content=combate(accion))) # Guardamos la información del combate para que el narrador pueda procesarla y generar un resumen coherente
                        finalizado = llm.invoke([
                            SystemMessage(content=f"Si el combate ha terminado, guarda la palabra 'FINALIZADO' en la variable finalizado"),
                            HumanMessage(content=resultado)
                        ]).content
                        if "FINALIZADO" in finalizado.upper():
                            comentario = llm.invoke([
                                SystemMessage(content=f"el jugador ha sacado un {valor} al tirar los dados en un D&D. Si es mayor a 12 ha acertado, si no, ha fracasado. Narra esto de forma genérica en 1 frase mostrando el valor del dado teniendo en cuenta este resultado: {resultado} y guardalo en la variable 'comentario'")
                            ])
                            print(comentario.content)
                            EnCombate = 0

                else:
                    print(narrador(resumen, user_input)) # Hacemos la llamada al narrador pasándole el resumen y la información introducida por el usuario
        else:
            print(narrador_inicio())
main()
