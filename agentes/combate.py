import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dados import tirardados
from config import STATS_PATH, COMBATE_PROMPT_PATH
import json

#tools = [combate(accion, datos)]
def combate():
    with open(COMBATE_PROMPT_PATH, 'r', encoding='utf-8') as f:
        system_prompt = f.read().strip()
    load_dotenv()
    llm = ChatOpenAI(model="gpt-4o", temperature=0.9)
    #messages = []
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        datos = json.load(f)
    combate_finalizado = False
    while not combate_finalizado:
        accion = input("Qué acción quieres realizar? (atacar o huir)")
        decision = llm.invoke([
            SystemMessage(content=f"Si el usuario escribe cualquier acción relacionada con atacar, guarda en la variable decision la palabra 'ATACAR'. Si el usuario escribe cualquier accion relacionada con huir, guarda en la variable decision la palabra 'HUIR'"),
            HumanMessage(content=accion)
        ]).content
        resultado_dado = tirardados()
        if "ATACAR" in decision.upper():
            #print("\n" + str(random_num) + "\n")
            if resultado_dado > 12:
                sistema = "ÉXITO: El jugador ha acertado"
                narracion = llm.invoke([
                    SystemMessage(content=COMBATE_PROMPT_PATH),
                    HumanMessage(content=f"Accion: {accion}, Dado: {resultado_dado}, Resultado: {sistema}")
                ]).content
                print(narracion.content)
                combate_finalizado = True
            else:
                sistema = "FALLO: El jugador ha fallado"
                datos["vida"] -= 10
                with open(STATS_PATH, 'w', encoding='utf-8') as f:
                    json.dump(datos, f)
                narracion = llm.invoke([
                    SystemMessage(content=COMBATE_PROMPT_PATH),
                    HumanMessage(content=f"Accion: {accion}, Dado: {resultado_dado}, Resultado: {sistema}")
                ]).content
                print(narracion.content)
        elif "HUIR" in decision.upper(): # Dado de 20 para huir
            print(resultado_dado)
            #print("\n" + str(random_num) + "\n")
            if resultado_dado > 10:
                sistema = "ÉXITO: El jugador ha huido"
                narracion = llm.invoke([
                    SystemMessage(content=COMBATE_PROMPT_PATH),
                    HumanMessage(content=f"Accion: {accion}, Dado: {resultado_dado}, Resultado: {sistema}")
                ]).content
                print(narracion.content)
                combate_finalizado = True
            else:
                sistema = "FALLO: El jugador ha fallado al huir"
                datos["vida"] -= 5
                with open(STATS_PATH, 'w', encoding='utf-8') as f:
                    json.dump(datos, f)
                narracion = llm.invoke([
                    SystemMessage(content=COMBATE_PROMPT_PATH),
                    HumanMessage(content=f"Accion: {accion}, Dado: {resultado_dado}, Resultado: {sistema}")
                ]).content
                print(narracion.content)
        