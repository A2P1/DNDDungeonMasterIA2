import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from tools.stats import get_status
from tools.resumen import mostrar_resumen
from tools.tool_combate import llamar_combate
from tools.dados import tirar_d20, tirar_dado
from tools.campana import get_progreso_campana, get_siguiente_beat, marcar_beat_completado, get_info_npc
from tools.entidades import get_enemigos_beat, get_estado_combate, get_info_entidad
from config import STATS_PATH

'''
    SystemMessage: Es el mensaje que se le da a la IA para que sepa cómo debe comportarse, en este caso, es el narrador de una partida de rol.
    HumanMessage: Lo que el usuario le dice a la IA, es decir, las acciones que quiere realizar en la partida.
    AIMessage: Lo que la IA responde al usuario, es decir, lo que ocurre en la partida.
'''
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import NARRADOR_PROMPT_PATH, RESUMEN_PATH, TEMPERATURE_NARRADOR # Importamos la ruta del prompt del narrador y la ruta del resumen

load_dotenv()
llm = ChatOpenAI(model="gpt-4o", temperature=TEMPERATURE_NARRADOR) # Cargamos el modelo de IA
'''with open(STATS_PATH, 'r', encoding='utf-8') as f: # Cargamos los stats del jugador
    datos = json.load(f)'''

with open(NARRADOR_PROMPT_PATH, 'r', encoding='utf-8') as f:
        system_prompt = f.read().strip()

llm_tools = llm.bind_tools([
    get_status, mostrar_resumen, tirar_d20, tirar_dado,
    get_progreso_campana, get_siguiente_beat, marcar_beat_completado, get_info_npc,
    get_enemigos_beat, get_estado_combate, get_info_entidad#, llamar_combate
])
Herramientas = [
    get_status, mostrar_resumen, tirar_d20, tirar_dado,
    get_progreso_campana, get_siguiente_beat, marcar_beat_completado, get_info_npc,
    get_enemigos_beat, get_estado_combate, get_info_entidad#, llamar_combate
]
mapa_herramientas = {t.name: t for t in Herramientas}


messages = [
        SystemMessage(content=system_prompt)
]
def narrador(user_input):
    respuesta = llm_tools.invoke(messages + [HumanMessage(content=user_input)])
    if respuesta.tool_calls:
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
                 SystemMessage(content=system_prompt), # Le decimos a la IA que no es la primera vez que interactúa en la partida
                HumanMessage(content=user_input),
                respuesta, # La petición original
                mensaje_herramienta # La respuesta de la función
            ])
                        
            print(respuesta_final.content)
            # HASTA AQUÍ ES FIJO PARA TODAS LAS TOOLS
    else:
        #prompts = []
        # Si hay resumen, es decir, ha empezado la partida, se añade y se imprime antes de la partida
        messages.append(SystemMessage(content=f'MODO_INICIO: NO')) # Le decimos a la IA que no es la primera vez que interactúa en la partida
        resumen_actual = RESUMEN_PATH.read_text(encoding='utf-8').strip() if RESUMEN_PATH.exists() else ""
        messages.append(SystemMessage(content=f'IMPORTANTE. No es tu primera intervención. Resumen: {resumen_actual}')) # Lo pasamos como SystemMessage en vez de HumanMessage para generar un historial sobre el que la IA se puede apoyar
            #print("GUANTANAMO")
            #print("Resumen: " + resumen)
        # Si no hay resumen, inicia la partida de 0

        # Guardamos la información del usuario
        messages.append(HumanMessage(content=user_input))
        #Generamos la respuesta de la ia
        respuesta = llm.invoke(messages)
        messages.append(AIMessage(content=respuesta.content)) # Guardamos su información

        resumen = llm.invoke([
            SystemMessage(content=f"Actualiza el resumen de la partida en un máximo de 2 frases. Mantén la continuidad y los detalles clave, no te inventes cosas no mencionadas"),
            HumanMessage(content=f"Resumen anterior: {resumen_actual} \nNueva información: {user_input} \nRespuesta de la IA: {respuesta.content}")
        ]).content.strip()
        RESUMEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RESUMEN_PATH, 'a', encoding='utf-8') as f:
            f.write(resumen + "\n")
        return respuesta.content

def narrador_inicio(campaña: dict = None):
    messages.append(SystemMessage(content=f'MODO_INICIO: SI'))
    if campaña:
        contexto = (
            f"CONTEXTO DE LA CAMPAÑA:\n"
            f"- Título: {campaña.get('titulo', '')}\n"
            f"- Gancho: {campaña.get('gancho', '')}\n"
            f"- Lugar: {campaña.get('ambientacion', {}).get('lugar', '')}\n"
            f"- Tono: {campaña.get('ambientacion', {}).get('tono', '')}\n"
            f"- Conflicto: {campaña.get('ambientacion', {}).get('conflicto', '')}\n"
        )
        messages.append(SystemMessage(content=contexto))
    messages.append(HumanMessage(content='Inicia la partida. Presenta la escena usando el gancho y la ambientación de la campaña.'))
    # Se genera el inicio de la partida
    respuesta = llm.invoke(messages)
        #print(respuesta.content)
    messages.append(AIMessage(content=respuesta.content)) # Le decimos a la IA que ya hay una primera respuesta
        
        # Generamos el primer resumen
    resumen = llm.invoke([
        SystemMessage(content="Resume en una frase corta lo que ha ocurrido"),
        HumanMessage(content=f"Resumen de la historia: {respuesta.content}") # Le pasamos esta info como HumanMessage porque es esa misma info la que tiene que resumir
    ]).content.strip()

    RESUMEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESUMEN_PATH, 'a', encoding='utf-8') as f:
        f.write(resumen + "\n")
    return respuesta.content
#narrador()




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

        with open(RESUMEN_PATH, 'a', encoding='utf-8') as f:
            f.write(resumen + "\n")
        return respuesta.content'''