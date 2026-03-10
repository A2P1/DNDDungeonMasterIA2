import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from tools.dados import dados_ataque
from config import STATS_PATH, COMBATE_PROMPT_PATH, RESUMEN_PATH
import json
from tools.comprobar_enemigo import comprobar_enemigo

load_dotenv()
llm = ChatOpenAI(model="gpt-4o", temperature=0.9)
llm_tools = llm.bind_tools([dados_ataque])
Herramientas = [dados_ataque]
mapa_herramientas = {t.name: t for t in Herramientas}

#tools = [combate(accion, datos)]
def combate():
    print("-")
    if comprobar_enemigo.invoke({}) == True:     
        '''with open(COMBATE_PROMPT_PATH, 'r', encoding='utf-8') as f:
        system_prompt = f.read().strip()'''

        #messages = []
        with open(STATS_PATH, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        combate_finalizado = False
        while not combate_finalizado:
            accion = input("Qué acción quieres realizar? (atacar o huir)")
            respuesta = llm_tools.invoke(accion) 
            print("-")
                
            if respuesta.tool_calls:
                    print("-")
                    for tool_call in respuesta.tool_calls:
                        # Buscamos la función en nuestro mapa y la ejecutamos
                        seleccionada = mapa_herramientas[tool_call["name"]]
                        respuesta_herramienta = seleccionada.invoke(tool_call["args"])
                        mensaje_herramienta = ToolMessage(
                            content=str(respuesta_herramienta), 
                            tool_call_id=tool_call["id"]
                        )
                        # 4. Invocación final: La IA ahora sí tiene los datos para hablar
                        respuesta_final = llm_tools.invoke([
                            SystemMessage(content="Narrador de D&D. Describe el resultado de los dados. NUNCA ofrezcas ayuda ni salgas del rol. Sé breve y visceral."),
                            HumanMessage(content=accion),
                            respuesta, # La petición original
                            mensaje_herramienta # La respuesta de la función
                        ])
                                    
                        print(respuesta_final.content)
                        # HASTA AQUÍ ES FIJO PARA TODAS LAS TOOLS
'''                    mensaje_herramienta = ToolMessage(
                        content=str(respuesta_herramienta), 
                        tool_call_id=tool_call["id"]
                    )
                    # 4. Invocación final: La IA ahora sí tiene los datos para hablar
                    respuesta_final = llm_tools.invoke([
                        HumanMessage(content=accion),
                        respuesta, # La petición original
                        mensaje_herramienta # La respuesta de la función
                    ])
                                        
                    print(respuesta_final.content)
                        # HASTA AQUÍ ES FIJO PARA TODAS LAS TOOLS'''
                    
'''        decision = llm.invoke([
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
                print(narracion.content)'''
        