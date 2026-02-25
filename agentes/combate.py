import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from dados import tirardados
import json

#tools = [combate(accion, datos)]
def combate(accion, datos):
    load_dotenv()
    llm = ChatOpenAI(model="gpt-4o", temperature=0.9)
    #messages = []


    decision = llm.invoke([
        SystemMessage(content=f"Si el usuario escribe cualquier acción relacionada con atacar, guarda en la variable decision la palabra 'ATACAR'. Si el usuario escribe cualquier accion relacionada con huir, guarda en la variable decision la palabra 'HUIR'"),
        HumanMessage(content=accion)
    ]).content
    resultado_dado = tirardados()
    if "ATACAR" in decision.upper():
        #print("\n" + str(random_num) + "\n")
        if resultado_dado > 12:
            print("buena")
            return "Combate ganado", str(resultado_dado)
        else:
            print("mala")
            #jugador["Vida"] -= enemigo["Ataque"]
            datos["vida"] -= 10
            with open('stats.json', 'w', encoding='utf-8') as f:
                json.dump(datos, f)
            print(datos["vida"])
            return "Combate perdido", str(resultado_dado)
    elif "HUIR" in decision.upper(): # Dado de 20 para huir
        print(resultado_dado)
        #print("\n" + str(random_num) + "\n")
        if resultado_dado > 10:
            return "Ha huído", str(resultado_dado)
        else:
            return "No ha huído", str(resultado_dado)