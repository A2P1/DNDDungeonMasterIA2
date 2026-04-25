import sys # Necesario para manipular el path antes de los otros imports
from pathlib import Path # Para manejar rutas de forma más cómoda
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz al path para que los imports del proyecto funcionen

import json # Para parsear JSONs si hace falta
from dotenv import load_dotenv # Para cargar la API key desde el .env
from langchain_openai import ChatOpenAI # El modelo de OpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage # Los tipos de mensaje que usamos en la conversación
from config import NARRADOR_PROMPT_PATH, RESUMEN_PATH, TEMPERATURE_NARRADOR # Rutas y configuración del narrador

from tools.stats import get_status # Tool para consultar el estado del jugador
from tools.resumen import mostrar_resumen # Tool para mostrar el resumen de la partida
from tools.dados import tirar_d20, tirar_dado # Tools para tirar dados
from tools.campana import get_progreso_campana, get_siguiente_beat, marcar_beat_completado, get_info_npc # Tools de campaña
from tools.entidades import get_enemigos_beat, get_estado_combate, get_info_entidad # Tools de entidades y combate
from tools.inventario import get_inventario, add_item_to_inventory, usar_item # Tools de inventario

load_dotenv() # Cargamos las variables de entorno para tener la API key disponible

llm = ChatOpenAI(model="gpt-4o", temperature=TEMPERATURE_NARRADOR) # El LLM del narrador con temperatura configurable

with open(NARRADOR_PROMPT_PATH, 'r', encoding='utf-8') as f: # Leemos el prompt del sistema desde el archivo de texto
    system_prompt = f.read().strip() # Lo guardamos limpio, sin espacios extra

llm_tools = llm.bind_tools([ # Versión del LLM que sabe usar las herramientas disponibles
    get_status, mostrar_resumen, tirar_d20, tirar_dado,
    get_progreso_campana, get_siguiente_beat, marcar_beat_completado, get_info_npc,
    get_enemigos_beat, get_estado_combate, get_info_entidad, get_inventario,
    add_item_to_inventory, usar_item
])

Herramientas = [ # Lista de todas las herramientas disponibles para el narrador
    get_status, mostrar_resumen, tirar_d20, tirar_dado,
    get_progreso_campana, get_siguiente_beat, marcar_beat_completado, get_info_npc,
    get_enemigos_beat, get_estado_combate, get_info_entidad, get_inventario,
    add_item_to_inventory, usar_item
]

mapa_herramientas = {t.name: t for t in Herramientas} # Diccionario nombre → herramienta para llamarlas por nombre fácilmente

messages = [ # Historial de mensajes de la sesión, empieza solo con el prompt del sistema
    SystemMessage(content=system_prompt)
]


def narrador(user_input): # Procesa la acción del jugador y devuelve la narración correspondiente
    respuesta = llm_tools.invoke(messages + [HumanMessage(content=user_input)]) # Le preguntamos al LLM qué hacer con la acción del jugador

    if respuesta.tool_calls: # Si el LLM quiere usar herramientas, las ejecutamos todas antes de pedir la respuesta final
        tool_messages = [] # Aquí guardamos los resultados de cada herramienta
        for tool_call in respuesta.tool_calls: # Recorremos todas las herramientas que el LLM quiere usar
            seleccionada = mapa_herramientas[tool_call["name"]] # Buscamos la herramienta por nombre en el mapa
            respuesta_herramienta = seleccionada.invoke(tool_call["args"]) # La ejecutamos con los args que el LLM eligió
            tool_messages.append(ToolMessage( # Empaquetamos el resultado como ToolMessage
                content=str(respuesta_herramienta), # El resultado de la herramienta como texto
                tool_call_id=tool_call["id"] # El id que vincula este resultado con la llamada original
            ))

        respuesta_final = llm_tools.invoke( # Pasamos messages[] para que el narrador conserve la memoria de turnos anteriores al usar tools
            messages + [
                HumanMessage(content=user_input), # La acción del jugador
                respuesta, # AIMessage con tool_calls — OpenAI exige que vaya entre el HumanMessage y los ToolMessage
                *tool_messages # Todos los resultados de las herramientas desempaquetados
            ]
        )

        # Persistimos el turno en messages[] para que la siguiente vuelta vea esta interacción.
        # Solo guardamos input y narración final: el resultado del tool ya quedó incorporado en la narración (no necesitamos cargar tool_calls/tool_results en el historial).
        messages.append(HumanMessage(content=user_input))
        messages.append(AIMessage(content=respuesta_final.content))

        # Actualizamos el resumen igual que el camino sin tools, para que los turnos con dado/consulta contribuyan a la memoria a medio plazo
        resumen_actual = RESUMEN_PATH.read_text(encoding='utf-8').strip() if RESUMEN_PATH.exists() else ""
        resumen = llm.invoke([
            SystemMessage(content="Actualiza el resumen de la partida en un máximo de 2 frases. Mantén la continuidad y los detalles clave, no te inventes cosas no mencionadas"),
            HumanMessage(content=f"Resumen anterior: {resumen_actual} \nNueva información: {user_input} \nRespuesta de la IA: {respuesta_final.content}")
        ]).content.strip()
        RESUMEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RESUMEN_PATH, 'a', encoding='utf-8') as f:
            f.write(resumen + "\n")

        return respuesta_final.content # Devolvemos solo el texto de la narración final

    else: # Si el LLM no necesita herramientas, generamos la respuesta directamente
        messages.append(SystemMessage(content='MODO_INICIO: NO')) # Le decimos que no es el inicio, ya hay contexto previo
        resumen_actual = RESUMEN_PATH.read_text(encoding='utf-8').strip() if RESUMEN_PATH.exists() else "" # Leemos el resumen si existe
        messages.append(SystemMessage(content=f'IMPORTANTE. No es tu primera intervención. Resumen: {resumen_actual}')) # Le pasamos el resumen como contexto

        messages.append(HumanMessage(content=user_input)) # Añadimos la acción del jugador al historial
        respuesta = llm.invoke(messages) # Generamos la respuesta narrativa
        messages.append(AIMessage(content=respuesta.content)) # Guardamos la respuesta en el historial para mantener continuidad

        resumen = llm.invoke([ # Actualizamos el resumen de la partida con lo que acaba de pasar
            SystemMessage(content="Actualiza el resumen de la partida en un máximo de 2 frases. Mantén la continuidad y los detalles clave, no te inventes cosas no mencionadas"),
            HumanMessage(content=f"Resumen anterior: {resumen_actual} \nNueva información: {user_input} \nRespuesta de la IA: {respuesta.content}")
        ]).content.strip() # Limpiamos el texto del resumen

        RESUMEN_PATH.parent.mkdir(parents=True, exist_ok=True) # Creamos la carpeta data/ si no existe todavía
        with open(RESUMEN_PATH, 'a', encoding='utf-8') as f: # Abrimos en modo append para no perder el historial de resúmenes
            f.write(resumen + "\n") # Añadimos el nuevo resumen al archivo

        return respuesta.content # Devolvemos la narración al jugador


def narrador_inicio(campaña: dict = None): # Genera la narración de apertura de la partida con el contexto de la campaña
    messages.append(SystemMessage(content='MODO_INICIO: SI')) # Le avisamos al LLM de que es el arranque de la partida

    if campaña: # Si nos pasan la campaña, construimos el contexto para que el LLM sepa dónde está el jugador
        contexto = ( # Juntamos los datos más relevantes de la campaña en un bloque de texto
            f"CONTEXTO DE LA CAMPAÑA:\n"
            f"- Título: {campaña.get('titulo', '')}\n"
            f"- Gancho: {campaña.get('gancho', '')}\n"
            f"- Lugar: {campaña.get('ambientacion', {}).get('lugar', '')}\n"
            f"- Tono: {campaña.get('ambientacion', {}).get('tono', '')}\n"
            f"- Conflicto: {campaña.get('ambientacion', {}).get('conflicto', '')}\n"
        )
        messages.append(SystemMessage(content=contexto)) # Lo añadimos como SystemMessage para que el LLM lo tome como referencia

    messages.append(HumanMessage(content='Inicia la partida. Presenta la escena usando el gancho y la ambientación de la campaña.')) # Le pedimos que arranque la historia

    respuesta = llm.invoke(messages) # Generamos la narración de apertura
    messages.append(AIMessage(content=respuesta.content)) # Guardamos la respuesta en el historial

    resumen = llm.invoke([ # Generamos el primer resumen de la partida para tener un punto de partida en el historial
        SystemMessage(content="Resume en una frase corta lo que ha ocurrido"),
        HumanMessage(content=f"Resumen de la historia: {respuesta.content}") # Le pasamos la narración de apertura para que la resuma
    ]).content.strip() # Limpiamos el resumen

    RESUMEN_PATH.parent.mkdir(parents=True, exist_ok=True) # Creamos la carpeta data/ si no existe
    with open(RESUMEN_PATH, 'a', encoding='utf-8') as f: # Guardamos el primer resumen en el archivo
        f.write(resumen + "\n")

    return respuesta.content # Devolvemos la narración de apertura al jugador
