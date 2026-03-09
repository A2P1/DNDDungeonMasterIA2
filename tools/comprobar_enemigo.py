from langchain_core.tools import tool
from config import RESUMEN_PATH
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
@tool
def comprobar_enemigo():
    '''Útil para saber si existe un enemigo al cual atacar en este momento'''
    llm = ChatOpenAI(model="gpt-4o", temperature=0.9)
    comprobar_enemigo = llm.invoke([
         SystemMessage(content=f"Si en el resumen actual de la partida hay un enemigo o entidad a la que se pueda atacar, responde con 'ENEMIGO'"),
            HumanMessage(content=f"Resumen actual: {RESUMEN_PATH}")
    ]).content
    if "ENEMIGO" in comprobar_enemigo.upper():
        return True
    return False