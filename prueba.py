import json
from langchain_core.tools import tool
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()
@tool
def get_status():
    '''
Útil para cuando el usuario pregunte por sus estadísticas de salud (vida), defensa o ataque. Devuelve el estado actual del personaje en formato JSON.
    '''
    with open('stats.json', 'r', encoding="utf-8") as f:
        return f.read()
    
llm = ChatOpenAI(model="gpt-4o", temperature=0)
llm_tools = llm.bind_tools([get_status])

diccionario = [get_status]
tools_map = {t.name: t for t in diccionario}
# 1. La IA pide la herramienta (Lo que ya tienes)
user = input("Escribe: ")
resultado_ia = llm_tools.invoke(user)

# 2. Si hay peticiones de herramientas...
if resultado_ia.tool_calls:
    for tool_call in resultado_ia.tool_calls:
        # Buscamos la función en nuestro mapa y la ejecutamos
        seleccionada = tools_map[tool_call["name"]]
        respuesta_herramienta = seleccionada.invoke(tool_call["args"])
        
        # 3. Le pasamos el resultado a la IA para que lo procese
        from langchain_core.messages import ToolMessage
        
        # Es vital pasarle el ID para que la IA sepa a qué petición responde
        mensaje_herramienta = ToolMessage(
            content=str(respuesta_herramienta), 
            tool_call_id=tool_call["id"]
        )
        
        # 4. Invocación final: La IA ahora sí tiene los datos para hablar
        respuesta_final = llm_tools.invoke([
            HumanMessage(content="¿Cuánta vida me queda?"),
            resultado_ia, # La petición original
            mensaje_herramienta # La respuesta de la función
        ])
        
        print(respuesta_final.content)
