import sys # Necesario para manipular el path antes de los otros imports
from pathlib import Path # Para manejar rutas de forma más cómoda
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz al path para que los imports del proyecto funcionen

import json # Para parsear JSONs si hace falta
from typing import Callable, Optional # Para tipar el callback opcional de streaming
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


def _generar(llm_obj, msgs: list, on_chunk: Optional[Callable[[str], None]]) -> str: # Helper: si hay callback, streamea por chunks; si no, batch con .invoke()
    if on_chunk is None: # Si no hay on_chunk, devuelve el texto de golpe
        return llm_obj.invoke(msgs).content
    
    #Si sí que hay on_chunk, devuelve el texto como si fuera una ia normal, generando texto palabra a palabra
    full_text = "" # Vamos acumulando los chunks para devolver el texto completo al final
    for chunk in llm_obj.stream(msgs): # .stream() devuelve trocitos según los va generando el LLM
        text = chunk.content or "" # Algunos chunks pueden venir con content vacío (metadatos), los ignoramos
        if text:
            on_chunk(text) # El caller decide qué hacer con el trozo (imprimirlo, mandarlo al front, etc.)
            full_text += text
    return full_text


def narrador(user_input, on_chunk: Optional[Callable[[str], None]] = None): # Procesa la acción del jugador y devuelve la narración. Si se pasa on_chunk, streamea
    respuesta = llm_tools.invoke(messages + [HumanMessage(content=user_input)]) # Primera llamada al LLM para comprobar si la respuesta requiere el uso de

    if respuesta.tool_calls: # Si el LLM quiere usar herramientas, las ejecutamos todas antes de pedir la respuesta final
        tool_messages = [] # Aquí guardamos los resultados de cada herramienta
        for tool_call in respuesta.tool_calls: # Recorremos todas las herramientas que el LLM quiere usar
            seleccionada = mapa_herramientas[tool_call["name"]] # Buscamos la herramienta por nombre en el mapa
            respuesta_herramienta = seleccionada.invoke(tool_call["args"]) # La ejecutamos con los args que el LLM eligió
            tool_messages.append(ToolMessage( # Empaquetamos el resultado como ToolMessage
                content=str(respuesta_herramienta), # El resultado de la herramienta como texto
                tool_call_id=tool_call["id"] # El id que vincula este resultado con la llamada original
            ))

        # Segunda llamada al LLM para generar el texto creado por las tools con el on_chunk
        # Pasamos messages[] para que el narrador recuerde el texto generado por las tools
        contenido_final = _generar(
            llm_tools,
            messages + [
                HumanMessage(content=user_input), # Le pasamos el input del usuario
                respuesta, # Las tools elegidas
                *tool_messages # Los resultados generado por las tools
            ],
            on_chunk
        )

        # Almacenamos la información del input del usuario y el contenido final generado por las tools
        messages.append(HumanMessage(content=user_input))
        messages.append(AIMessage(content=contenido_final))

        # Actualizamos el resumen con la respuesta de las tools y el input del usuario, para que el LLM pueda generar una continuación a la historia
        resumen_actual = RESUMEN_PATH.read_text(encoding='utf-8').strip() if RESUMEN_PATH.exists() else ""
        resumen = llm.invoke([ # El resumen no se streamea: es interno, el usuario no lo ve
            SystemMessage(content="Actualiza el resumen de la partida en un máximo de 2 frases. Mantén la continuidad y los detalles clave, no te inventes cosas no mencionadas"),
            HumanMessage(content=f"Resumen anterior: {resumen_actual} \nNueva información: {user_input} \nRespuesta de la IA: {contenido_final}")
        ]).content.strip()
        RESUMEN_PATH.parent.mkdir(parents=True, exist_ok=True) # Creamos la ruta DATA por si es la primera vez ejecutando el programa
        with open(RESUMEN_PATH, 'a', encoding='utf-8') as f:
            f.write(resumen + "\n")

        return contenido_final # Devolvemos el texto de la narración final de las tools

    else: # Si se confirma que el usuario no necesita tools para esta interacción, se continúa la historia
        messages.append(SystemMessage(content='MODO_INICIO: NO')) # Declaramos al LLM que no es un inicio de historia
        resumen_actual = RESUMEN_PATH.read_text(encoding='utf-8').strip() if RESUMEN_PATH.exists() else "" # Leemos el resumen actual
        messages.append(SystemMessage(content=f'IMPORTANTE. No es tu primera intervención. Resumen: {resumen_actual}')) # Le pasamos el resumen para que tenga contexto

        messages.append(HumanMessage(content=user_input)) # Almacenamos el input del usuario
        contenido = _generar(llm, messages, on_chunk) # Generamos el texto narrativo teniendo en cuenta el resumen y el input. 
        messages.append(AIMessage(content=contenido)) # Almacenamos la respuesta de la IA para el resumen

        resumen = llm.invoke([ # Actualizamos el resumen de la partida con lo que acaba de generar el LLM - Resumen anterior, el input del usuario y el nuevo contenido generado
            SystemMessage(content="Actualiza el resumen de la partida en un máximo de 2 frases. Mantén la continuidad y los detalles clave, no te inventes cosas no mencionadas"),
            HumanMessage(content=f"Resumen anterior: {resumen_actual} \nNueva información: {user_input} \nRespuesta de la IA: {contenido}")
        ]).content.strip() # Almacenamos solo el texto del resumen. Si no hacemos esto devuelve un JSON bastante feo

        RESUMEN_PATH.parent.mkdir(parents=True, exist_ok=True) # Creamos la carpeta DATA si no existe todavía
        with open(RESUMEN_PATH, 'a', encoding='utf-8') as f: # Actualizamos el resumen de la historia con la nueva narración generada
            f.write(resumen + "\n") # Añadimos el nuevo resumen al archivo

        return contenido # Devolvemos el contenido generado


def narrador_inicio(campaña: dict = None, on_chunk: Optional[Callable[[str], None]] = None): # Genera el inicio de la historia
    messages.append(SystemMessage(content='MODO_INICIO: SI')) # Declaramos al LLM que tiene que comenzar la historia
    if campaña: # Si existe la campaña generada por el director, construimos el contexto para que el LLM genere el inicio con la ambientación
        contexto = (
            f"CONTEXTO DE LA CAMPAÑA:\n"
            f"- Título: {campaña.get('titulo', '')}\n"
            f"- Gancho: {campaña.get('gancho', '')}\n"
            f"- Lugar: {campaña.get('ambientacion', {}).get('lugar', '')}\n"
            f"- Tono: {campaña.get('ambientacion', {}).get('tono', '')}\n"
            f"- Conflicto: {campaña.get('ambientacion', {}).get('conflicto', '')}\n"
        )
        messages.append(SystemMessage(content=contexto)) # Almacenamos el contexto

    messages.append(HumanMessage(content='Inicia la partida. Presenta la escena usando el gancho y la ambientación de la campaña.')) # Genera y almacena la primera escena

    contenido = _generar(llm, messages, on_chunk) # Imprimimos el texto a partir del contexto y la primera escena
    messages.append(AIMessage(content=contenido)) # Guardamos la respuesta generada para el futuro resumen

    resumen = llm.invoke([ # Generamos el primer resumen de la partida
        SystemMessage(content="Resume en una frase corta lo que ha ocurrido"),
        HumanMessage(content=f"Resumen de la historia: {contenido}") # Le pasamos la narración de apertura para que la resuma
    ]).content.strip() # Limpiamos el resumen

    RESUMEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESUMEN_PATH, 'a', encoding='utf-8') as f: # Guardamos el primer resumen en el archivo
        f.write(resumen + "\n")

    return contenido # Devolvemos la narración de apertura al jugador
