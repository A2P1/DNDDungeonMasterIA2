import json # Para leer y escribir los JSONs del estado de la partida
import re # Para extraer JSON de bloques markdown que devuelve el LLM
from dotenv import load_dotenv # Para cargar la API key desde el .env
from langchain_openai import ChatOpenAI # El LLM que usamos para detectar intenciones
from langchain_core.messages import SystemMessage, HumanMessage # Tipos de mensaje para el LLM detector
from langchain_core.output_parsers import JsonOutputParser # Para parsear las respuestas JSON del LLM

from agentes.Narrador import narrador, narrador_inicio, resetear_memoria # El narrador principal de la partida
from agentes.director import generar_campaña, campaña_existe, cargar_campaña # Para crear y cargar la campaña
from agentes.enriquecedor import enriquecer_entidades, entidades_existen # Para generar las fichas de enemigos y NPCs
from agentes.combate import combate # El agente de combate
from agentes.creador_personaje import crear_personaje, personaje_existe # Para crear la ficha del jugador

from tools.campana import get_siguiente_beat, marcar_beat_completado # Para navegar por los beats de la campaña
from tools.inventario import add_item_to_inventory # Para añadir loot al inventario del jugador
from tools.entidades import get_info_entidad # Para consultar el estado de una entidad concreta

from config import RESUMEN_PATH, CAMPAIGN_PATH, ENTIDADES_PATH, STATS_PATH, DIARIO_PATH, MODEL_NAME, TEMPERATURE_LOGICA # Rutas y configuración general
from ui import (narrador_msg, combate_msg, victoria_msg, derrota_msg, # Funciones batch de la UI (siguen usándose en sitios sin streaming)
                sistema_msg, titulo_msg, prompt_jugador, prompt_input,
                narrador_msg_inicio, narrador_msg_chunk, narrador_msg_fin, # Helpers de streaming para narración estándar
                victoria_msg_inicio, victoria_msg_chunk, victoria_msg_fin, # Helpers de streaming para narración de victoria
                derrota_msg_inicio, derrota_msg_chunk, derrota_msg_fin) # Helpers de streaming para narración de derrota

_llm_detector = ChatOpenAI(model=MODEL_NAME, temperature=TEMPERATURE_LOGICA) # LLM de baja temperatura para decisiones lógicas (detectar ataques, objetivos...)
_parser_detector = JsonOutputParser() # Parser para las respuestas JSON del LLM detector


def iniciar (tema, personaje):
    if campaña_existe():
        campaña = cargar_campaña()
        if not personaje_existe():
            stats = crear_personaje(personaje)
        else:
            stats = cargar_stats()
    else:
        stats = crear_personaje(personaje)
        campaña = generar_campaña(tema, personaje)
        if not entidades_existen(): 
            enriquecer_entidades(campaña) 
    
    return {"campaña": campaña, "stats": stats, "narracion_inicio": narrar_inicio_partida()}

def comprobarCampaña() -> bool: # Comprobamos si existe la campaña
    if campaña_existe():
        return True
    return False



def cargar_stats() -> dict: # Cargamos los datos del jugador
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def borrar_campaña():
    for path in [CAMPAIGN_PATH, ENTIDADES_PATH, STATS_PATH, RESUMEN_PATH, DIARIO_PATH]:
        if path.exists():
            path.unlink()
    resetear_memoria() # La ventana del narrador es global de módulo: si no la limpiamos, arrastra el contexto de la partida anterior

def _get_entidades_presentes() -> list: # Devuelve las entidades vivas del beat actual (enemigos y NPCs registrados en entidades.json)
    raw = get_siguiente_beat.invoke({}) 
    if raw == "CAMPAÑA COMPLETADA": 
        return []

    data = json.loads(raw) 
    beat = data.get("beat", {}) 
    beat_id = beat.get("id", "") 

    if not ENTIDADES_PATH.exists(): 
        return []

    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
        entidades = json.load(f)

    presentes = [] 

    for e in entidades.get("enemigos", []): 
        if e.get("beat_origen") == beat_id and e.get("estado") == "vivo":
            e_copy = dict(e)
            e_copy["tipo_entidad"] = "enemigo" 
            presentes.append(e_copy)

    npc_nombre = beat.get("npc") 
    if npc_nombre: 
        for npc in entidades.get("npcs", []):
            if npc.get("nombre", "").lower() == npc_nombre.lower() and npc.get("estado") == "vivo":
                npc_copy = dict(npc) 
                npc_copy["tipo_entidad"] = "npc" 
                presentes.append(npc_copy)               
    return presentes 

def _generar_enemigo_narrativo(user_input: str, resumen: str) -> list: # Genera un nuevo enemigo que no ha sido generado al crear la campaña
    llm_gen = ChatOpenAI(model=MODEL_NAME, temperature=0.3) 
    respuesta = llm_gen.invoke([ 
        SystemMessage(content=(
            "Eres un generador de stats de enemigos para D&D. "
            "Basándote en el contexto narrativo, genera stats para el o los enemigos "
            "que el jugador quiere atacar. "
            "Responde SOLO con JSON válido (lista), sin texto extra:\n"
            "[\n"
            "  {\n"
            '    "id": "temp_<nombre_sin_espacios>_1",\n'
            '    "nombre": "<nombre legible>",\n'
            '    "tipo": <raza>,\n'
            '    "beat_origen": "temp",\n'
            '    "estado": "vivo",\n'
            '    "vida_max": <10-20>,\n'
            '    "vida_actual": <igual a vida_max>,\n'
            '    "ac": <10-13>,\n'
            '    "dado_daño": "1d6",\n'
            '    "xp": 50,\n'
            '    "atributos": {"fue": <1-5>, "des": <1-5>, "con": <1-5>, "int": <1-5>, "sab": <1-5>, "car": <1-5>},\n'
            '    "arma": <depende del contexto en el que se encuentre el enemigo>,\n'
            '    "descripcion": "<descripción breve>"\n'
            "  }\n"
            "]\n"
            "Genera solo los enemigos que el jugador menciona atacar directamente. "
            "Ajusta los stats al tipo de personaje que aparece en el contexto."
        )),
        HumanMessage(content=f"Contexto narrativo reciente:\n{resumen}\n\nAcción del jugador: {user_input}")
    ])
    try:
        contenido = respuesta.content 
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', contenido) 
        if match:
            contenido = match.group(1).strip() 

        enemigos = json.loads(contenido) 
        if not isinstance(enemigos, list): 
            return []

        with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f: 
            entidades = json.load(f)

        ids_existentes = {e["id"] for e in entidades.get("enemigos", [])} 
        nuevos = [] 

        for e in enemigos: # Guardamos el id del enemigo en una lista de nuevos enemigos
            if e.get("id") and e["id"] not in ids_existentes:
                entidades["enemigos"].append(e)
                e_con_tipo = dict(e) 
                e_con_tipo["tipo_entidad"] = "enemigo"
                nuevos.append(e_con_tipo) 

        with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f: 
            json.dump(entidades, f, indent=2, ensure_ascii=False)

        return nuevos 

    except Exception as e: # Si algo falla, lo mostramos en modo debug y devolvemos lista vacía
        sistema_msg(f"[DEBUG] Excepción en _generar_enemigo_narrativo: {e}")
        return []
    
def _detectar_intento_ataque(accion: str, resumen: str):
    respuesta = _llm_detector.invoke([
        SystemMessage(content=(
            "Eres un árbitro en un juego de rol que detecta DOS COSAS:" \
            "1. ¿El usuario quiere atacar, herir o agredir a otra entidad como una persona, animal, entidad?"
            "2. ¿El contexto narrativo menciona alguna entidad que pueda ser atacada (NPC, enemigo, animal)?" \
            "Responde SOLO con JSON válido, sin texto extra:\n"
            "{\"quiere_atacar\": true/false, \"hay_objetivo_en_escena\": true/false}"
        )),
        HumanMessage(content=(f"Contexto narrativo actual: {resumen}, Acción del jugador: {accion}"))
    ])
    try:
        resultado = _parser_detector.parse(respuesta.content)
        return bool(resultado.get("quiere_atacar", False)), bool(resultado.get("hay_objetivo_en_escena", False))
    except Exception as e: 
        return False # Si algo falla, se asume que no hay intento de ataque
    
def _hay_entidad_atacable(user_input: str, resumen: str) -> bool: # Comprueba si hay alguien presente a quien atacar según el contexto narrativo
    respuesta = _llm_detector.invoke([ # Preguntamos al LLM si hay un objetivo razonable en la escena
        SystemMessage(content=(
            "Eres un árbitro de un juego de rol que, dado el resumen narrativo reciente y la acción del jugador, determina si"
            "hay alguna entidad (persona, criatura, monstruo) presente en la escena a la que "
            "el jugador pueda atacar razonablemente. "
            "No cuenten objetos inanimados como árboles, puertas o paredes. "
            "Responde SOLO con JSON válido, sin texto extra: "
            "{\"hay_objetivo\": true} o {\"hay_objetivo\": false}"
        )),
        HumanMessage(content=f"Resumen narrativo reciente:\n{resumen}\n\nAcción del jugador: {user_input}")
    ])
    try:
        contenido = respuesta.content
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', contenido) 
        if match:
            contenido = match.group(1).strip() 
        resultado = json.loads(contenido) 
        return bool(resultado.get("hay_objetivo", False)) 
    except Exception:
        return False 



def narrar_inicio_partida():
    campaña = cargar_campaña()
    narracion_inicio = narrador_inicio(campaña)
    return {"tipo": "narracion", "texto": narracion_inicio}

def procesar_accion(accion: str):
    if not campaña_existe(): # Si todavía no hay campaña, el único camino válido es generar la apertura
        return narrar_inicio_partida()

    contexto = DIARIO_PATH.read_text(encoding='utf-8').strip() if DIARIO_PATH.exists() else "" # Contexto narrativo para los detectores: el diario sustituye al antiguo resumen.txt
    quiere_atacar, hay_objetivo = _detectar_intento_ataque(accion, contexto)
    if quiere_atacar and hay_objetivo:
        entidades = _get_entidades_presentes()
        if not entidades and _hay_entidad_atacable(accion, contexto):
            entidades = _generar_enemigo_narrativo(accion, contexto)
        if entidades:
            beat1 = entidades[0].get("beat_origen", "temp")
            return {"tipo": "combate_iniciado", "entidades": entidades, "texto": combate(entidades), "beat_id": beat1} # Como el tema del combate se gestiona a través de la api, aquí solo devolvemos que el combate ha iniciado
    narracion = narrador(accion)
    return {"tipo": "narracion", "texto": narracion}

                

