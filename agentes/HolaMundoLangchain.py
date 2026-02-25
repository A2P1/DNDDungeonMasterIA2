import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

'''
    SystemMessage: Es el mensaje que se le da a la IA para que sepa cómo debe comportarse, en este caso, es el narrador de una partida de rol.
    HumanMessage: Lo que el usuario le dice a la IA, es decir, las acciones que quiere realizar en la partida.
    AIMessage: Lo que la IA responde al usuario, es decir, lo que ocurre en la partida.
'''
with open('Narradorprompt.txt', 'r', encoding='utf-8') as f:
        system_prompt = f.read().strip()

load_dotenv()
llm = ChatOpenAI(model="gpt-4o", temperature=0.9)
messages = [
        SystemMessage(content=system_prompt)
]
def narrador(resumen, user_input):

    #prompts = []
    # Si hay resumen, es decir, ha empezado la partida, se añade y se imprime antes de la partida
    messages.append(SystemMessage(content=f'MODO_INICIO: NO')) # Le decimos a la IA que no es la primera vez que interactúa en la partida
    messages.append(SystemMessage(content=f'IMPORTANTE. No es tu primera intervención. Resumen: {resumen}')) # Lo pasamos como SystemMessage en vez de HumanMessage para generar un historial sobre el que la IA se puede apoyar
        #print("GUANTANAMO")
        #print("Resumen: " + resumen)
    # Si no hay resumen, inicia la partida de 0
    '''else:
        messages.append(SystemMessage(content=f'MODO_INICIO: SI')) # Le decimos a la IA que es el inicio de la partida para que sepa que no hay resumen previo
        messages.append(HumanMessage(content='Inicia la partida de 0, Presenta la partida'))
        # Se genera el inicio de la partida
        respuesta = llm.invoke(messages)
        #print(respuesta.content)
        messages.append(AIMessage(content=respuesta.content)) # Le decimos a la IA que ya hay una primera respuesta
        
        # Generamos el primer resumen
        resumen = llm.invoke([
            SystemMessage(content="Resume en una frase corta lo que ha ocurrido"),
            HumanMessage(content=f"Resumen de la historia: {respuesta.content}") # Le pasamos esta info como HumanMessage porque es esa misma info la que tiene que resumir
        ]).content.strip()

        with open('resumen.txt', 'a', encoding='utf-8') as f:
            f.write(resumen + "\n")
        return respuesta.content'''
    # Guardamos la información del usuario
    messages.append(HumanMessage(content=user_input))
    #Generamos la respuesta de la ia
    respuesta = llm.invoke(messages)
    messages.append(AIMessage(content=respuesta.content)) # Guardamos su información

    resumen = llm.invoke([
        SystemMessage(content=f"Actualiza el resumen de la partida en un máximo de 2 frases. Mantén la continuidad y los detalles clave, no te inventes cosas no mencionadas"),
        HumanMessage(content=f"Resumen anterior: {resumen} \nNueva información: {user_input} \nRespuesta de la IA: {respuesta.content}")
    ]).content.strip()
    with open('resumen.txt', 'a', encoding='utf-8') as f:
        f.write(resumen + "\n")
    return respuesta.content

def narrador_inicio():
    messages.append(SystemMessage(content=f'MODO_INICIO: SI'))
    messages.append(HumanMessage(content='Inicia la partida de 0, Presenta la partida'))
    # Se genera el inicio de la partida
    respuesta = llm.invoke(messages)
        #print(respuesta.content)
    messages.append(AIMessage(content=respuesta.content)) # Le decimos a la IA que ya hay una primera respuesta
        
        # Generamos el primer resumen
    resumen = llm.invoke([
        SystemMessage(content="Resume en una frase corta lo que ha ocurrido"),
        HumanMessage(content=f"Resumen de la historia: {respuesta.content}") # Le pasamos esta info como HumanMessage porque es esa misma info la que tiene que resumir
    ]).content.strip()

    with open('resumen.txt', 'a', encoding='utf-8') as f:
        f.write(resumen + "\n")
    return respuesta.content   
#narrador()