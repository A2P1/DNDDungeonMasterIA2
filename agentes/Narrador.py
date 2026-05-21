import sys # Necesario para manipular el path antes de los otros imports
from pathlib import Path # Para manejar rutas de forma más cómoda
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz al path para que los imports del proyecto funcionen

import json # Para leer stats.json y construir el resumen del jugador a inyectar en cada turno
from typing import Callable, Optional # Para tipar el callback opcional de streaming
from dotenv import load_dotenv # Para cargar la API key desde el .env
from langchain_openai import ChatOpenAI # El modelo de OpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage # Los tipos de mensaje que usamos en la conversación
from config import NARRADOR_PROMPT_PATH, STATS_PATH, TEMPERATURE_NARRADOR, NARRADOR_MODEL # Rutas y configuración del narrador

from agentes.secretario import cargar_diario, guardar_diario, extraer_delta, aplicar_delta # Memoria estructurada a largo plazo (sustituye a resumen.txt)

from tools.stats import get_status # Tool para consultar el estado del jugador
from tools.resumen import mostrar_resumen # Tool para mostrar el resumen de la partida
from tools.dados import tirar_d20, tirar_dado # Tools para tirar dados
from tools.campana import get_progreso_campana, get_siguiente_beat, marcar_beat_completado, get_info_npc # Tools de campaña
from tools.entidades import get_enemigos_beat, get_estado_combate, get_info_entidad # Tools de entidades y combate
from tools.inventario import get_inventario, add_item_to_inventory, usar_item # Tools de inventario

load_dotenv() # Cargamos las variables de entorno para tener la API key disponible

llm = ChatOpenAI(model=NARRADOR_MODEL, temperature=TEMPERATURE_NARRADOR) # El LLM del narrador. FIX-15: modelo configurable por agente (antes hardcodeado "gpt-4o")

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

messages = [ # Ventana deslizante: messages[0] = prompt, el resto son los últimos pares Human/AI. El diario se inyecta en cada llamada pero no se acumula aquí.
    SystemMessage(content=system_prompt)
]
WINDOW_MESSAGES = 20 # Tamaño máximo de la ventana: 10 turnos × 2 mensajes (Human + AI)


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


def _diario_msg() -> SystemMessage: # Lee el diario actual del disco y lo envuelve como SystemMessage para inyectarlo en la llamada
    diario = cargar_diario()
    return SystemMessage(content=f"DIARIO (memoria a largo plazo):\n{diario.model_dump_json(indent=2, exclude_none=True)}")


def _beat_msg() -> SystemMessage: # Consulta el beat activo de la campaña y lo envuelve para inyectarlo como contexto narrativo
    raw = get_siguiente_beat.invoke({})
    if raw == "CAMPAÑA COMPLETADA":
        return SystemMessage(content="BEAT ACTUAL: campaña completada. La historia principal ha concluido — narra epílogo o aventura libre.")
    return SystemMessage(content=f"BEAT ACTUAL (escena que el director ha preparado, úsalo como guía narrativa):\n{raw}")


def _stats_msg() -> SystemMessage: # Ficha completa del jugador. Crítico: sin esto el narrador inventa quién es el jugador y qué lleva
    if not STATS_PATH.exists(): # Defensa: si todavía no se ha creado el personaje, devolvemos un marcador inocuo
        return SystemMessage(content="JUGADOR: aún no creado")
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        stats = json.load(f)
    return SystemMessage(content=f"JUGADOR (ficha completa, nombre/clase/HP/atributos/inventario):\n{json.dumps(stats, indent=2, ensure_ascii=False)}")


def _truncar_ventana() -> None: # Mantiene messages[0] (prompt fijo) + últimos WINDOW_MESSAGES pares Human/AI, descarta el resto
    if len(messages) > 1 + WINDOW_MESSAGES:
        del messages[1:-WINDOW_MESSAGES]


def _actualizar_diario(accion: str, narracion: str) -> None: # Tras un turno, pide al secretario que extraiga el delta y lo persiste en el diario
    diario = cargar_diario()
    delta = extraer_delta(accion, narracion, diario)
    guardar_diario(aplicar_delta(diario, delta))


def resetear_memoria() -> None: # Vacía la ventana dejando solo el SystemMessage del prompt. Se llama al iniciar campaña nueva para que no arrastre contexto de la anterior.
    del messages[1:]


MAX_VUELTAS_REACT = 5 # FIX-07: tope de rondas del bucle de agente (ReAct) para evitar bucles infinitos


def narrador(user_input, on_chunk: Optional[Callable[[str], None]] = None): # Procesa la acción del jugador y devuelve la narración. Si se pasa on_chunk, streamea
    mensajes = [messages[0], _diario_msg(), _beat_msg(), _stats_msg(), *messages[1:], HumanMessage(content=user_input)] # Base de contexto: prompt + diario + beat + ficha jugador + ventana + acción
    partes_narracion = [] # FIX-06 v3: acumulamos la prosa de CADA ronda del ReAct. Antes solo se devolvía la última y se perdía la verbalización ("Tírame una de X") de las rondas intermedias

    respuesta = llm_tools.invoke(mensajes) # Primera llamada al LLM
    for _ in range(MAX_VUELTAS_REACT): # FIX-07: ReAct loop — el LLM puede encadenar tools y razonar entre llamadas
        if respuesta.content and respuesta.content.strip(): # Guardamos toda prosa intermedia: verbalización de tiradas, transiciones, etc.
            partes_narracion.append(respuesta.content.strip())
        if not respuesta.tool_calls: # El LLM ya no quiere más tools → este content es la narración final
            break
        mensajes = mensajes + [respuesta] # Añadimos la AIMessage con las tool_calls que pidió
        for tool_call in respuesta.tool_calls: # Ejecutamos cada tool pedida en esta ronda
            try:
                seleccionada = mapa_herramientas[tool_call["name"]]
                resultado = str(seleccionada.invoke(tool_call["args"]))
            except Exception as e: # FIX-07: si el tool falla, el LLM ve el error y puede reintentar (en vez de crashear el turno)
                resultado = f"Error ejecutando {tool_call['name']}: {e}"
            mensajes.append(ToolMessage(content=resultado, tool_call_id=tool_call["id"]))
        respuesta = llm_tools.invoke(mensajes) # Siguiente vuelta: el LLM razona con los resultados de las tools

    if respuesta.tool_calls: # MAX_VUELTAS_REACT alcanzado sin cierre — forzamos narración con llm (sin tools) para garantizar texto
        cierre = _generar(llm, mensajes, on_chunk)
        if cierre and cierre.strip():
            partes_narracion.append(cierre.strip())

    contenido_final = "\n\n".join(partes_narracion) # Une verbalización + outcome para que el jugador vea el flujo completo del DM
    if on_chunk and not respuesta.tool_calls: # Streaming: emitimos el texto acumulado por chunks (la última ronda no se re-invoca, ya tenemos su contenido)
        on_chunk(contenido_final)

    messages.append(HumanMessage(content=user_input)) # Persistimos el turno en la ventana deslizante
    messages.append(AIMessage(content=contenido_final))
    _truncar_ventana()
    _actualizar_diario(user_input, contenido_final) # El secretario extrae y persiste lo digno de recordar a largo plazo
    return contenido_final


def narrador_inicio(campaña: dict = None, on_chunk: Optional[Callable[[str], None]] = None): # Genera el inicio de la historia
    inicio_flag = SystemMessage(content='MODO_INICIO: SI') # Bandera SOLO para esta llamada (no se persiste en messages[] para que no contamine los turnos siguientes)
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

    contenido = _generar(llm, [messages[0], _diario_msg(), _beat_msg(), _stats_msg(), inicio_flag, *messages[1:]], on_chunk) # Inicio: prompt + diario (vacío) + beat 1 + ficha del jugador + bandera de inicio (temporal) + contexto general
    messages.append(AIMessage(content=contenido)) # Guardamos la respuesta generada en la ventana
    _truncar_ventana() # Mantenemos la ventana acotada
    _actualizar_diario('Inicio de la partida', contenido) # El secretario captura los hechos iniciales (lugar, gancho, NPCs presentes)

    return contenido # Devolvemos la narración de apertura al jugador
