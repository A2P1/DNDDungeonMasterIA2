import json # Para leer y escribir los JSONs del estado de la partida
import re # Para extraer JSON de bloques markdown que devuelve el LLM
from typing import Optional # Para tipar el nombre_objetivo en el schema de detección
from dotenv import load_dotenv # Para cargar la API key desde el .env
from pydantic import BaseModel # Para el schema de detección de ataque con structured output
from langchain_openai import ChatOpenAI # El LLM que usamos para detectar intenciones
from langchain_core.messages import SystemMessage, HumanMessage # Tipos de mensaje para el LLM detector

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

class DeteccionAtaque(BaseModel): # FIX-11: schema único y estricto para decidir si la acción del jugador entra a combate
    quiere_atacar: bool # ¿El jugador expresa intención DIRECTA de atacar/herir/agredir?
    objetivo_es_criatura: bool # ¿El objetivo es persona/criatura/animal vivo (no objeto inanimado)?
    objetivo_claro: bool # ¿Hay UN objetivo concreto identificable en el contexto, no inventado?
    nombre_objetivo: Optional[str] = None # Nombre exacto del objetivo si está claro (para alimentar al generador de stats)


_llm_deteccion = ChatOpenAI(model=MODEL_NAME, temperature=TEMPERATURE_LOGICA).with_structured_output(DeteccionAtaque) # FIX-11: structured output que unifica los 2 detectores anteriores


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

def _generar_enemigo_narrativo(user_input: str, resumen: str, nombre_objetivo: str = "") -> list: # Genera un nuevo enemigo que no ha sido generado al crear la campaña. FIX-11: nombre_objetivo viene del detector y aterriza la generación a una entidad concreta
    jugador_nombre = cargar_stats().get("nombre", "") if STATS_PATH.exists() else "" # Necesario para evitar que el LLM bautice al enemigo con el nombre del jugador
    llm_gen = ChatOpenAI(model=MODEL_NAME, temperature=0.3)
    hint_objetivo = f"El jugador apunta específicamente a '{nombre_objetivo}'. Genera SOLO esa entidad como enemigo, con stats coherentes con su descripción en el contexto. " if nombre_objetivo else ""
    respuesta = llm_gen.invoke([
        SystemMessage(content=(
            "Eres un generador de stats de enemigos para D&D. "
            "Basándote en el contexto narrativo, genera stats para el o los enemigos "
            "que el jugador quiere atacar. "
            f"{hint_objetivo}"
            f"IMPORTANTE: el jugador se llama '{jugador_nombre}'. NUNCA uses ese nombre para el enemigo — el enemigo es una entidad distinta del jugador. "
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

        if jugador_nombre: # Defensa post-LLM: descartamos cualquier enemigo bautizado con el nombre del jugador, pese a la instrucción del prompt
            enemigos = [e for e in enemigos if e.get("nombre", "").strip().lower() != jugador_nombre.strip().lower()]
            if not enemigos:
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
    
def _detectar_ataque(accion: str, contexto: str) -> dict: # FIX-11: detección unificada. Solo activa combate si las 3 condiciones son true Y hay un objetivo nombrado
    try:
        result = _llm_deteccion.invoke([
            SystemMessage(content=(
                "Eres un árbitro en un juego de rol. Analiza la acción del jugador y el contexto narrativo y determina con RIGOR:\n"
                "1. quiere_atacar: ¿el jugador expresa intención DIRECTA de atacar/herir/agredir físicamente a una entidad? "
                "Ejemplos SÍ: 'le pego', 'ataco al guardia', 'le tiro un puñetazo'. "
                "Ejemplos NO: 'rompo la puerta' (objeto), 'examino el cofre', 'huyo', 'le hablo', 'le pregunto'.\n"
                "2. objetivo_es_criatura: ¿el objetivo es una persona/criatura/animal vivo? "
                "Objetos inanimados (muros, puertas, muebles, árboles, cofres) → false.\n"
                "3. objetivo_claro: ¿hay UN objetivo CONCRETO e IDENTIFICABLE mencionado en el contexto narrativo? "
                "Si el jugador dice 'le pego' o 'ataco' pero NADIE está mencionado en la escena cercana → false. "
                "NO inventes objetivos: el contexto debe nombrarlos o describirlos explícitamente.\n"
                "4. nombre_objetivo: si el objetivo está claro, copia su nombre exacto tal como aparece en el contexto (NPC, enemigo, animal). "
                "Si no está claro, déjalo en null."
            )),
            HumanMessage(content=f"Contexto narrativo:\n{contexto}\n\nAcción del jugador: {accion}")
        ])
        return result.model_dump(exclude_none=True)
    except Exception:
        return {"quiere_atacar": False, "objetivo_es_criatura": False, "objetivo_claro": False}



def narrar_inicio_partida():
    campaña = cargar_campaña()
    narracion_inicio = narrador_inicio(campaña)
    return {"tipo": "narracion", "texto": narracion_inicio}

def procesar_accion(accion: str):
    if not campaña_existe(): # Si todavía no hay campaña, el único camino válido es generar la apertura
        return narrar_inicio_partida()

    contexto = DIARIO_PATH.read_text(encoding='utf-8').strip() if DIARIO_PATH.exists() else "" # Contexto narrativo para el detector: el diario sustituye al antiguo resumen.txt
    deteccion = _detectar_ataque(accion, contexto) # FIX-11: detección unificada (quiere_atacar + objetivo_es_criatura + objetivo_claro)
    if deteccion.get("quiere_atacar") and deteccion.get("objetivo_es_criatura") and deteccion.get("objetivo_claro"):
        entidades = _get_entidades_presentes()
        if not entidades and deteccion.get("nombre_objetivo"): # Solo fabricamos enemigo si tenemos un nombre concreto del contexto (evita inventar enemigos de la nada)
            entidades = _generar_enemigo_narrativo(accion, contexto, deteccion["nombre_objetivo"])
        if entidades:
            beat1 = entidades[0].get("beat_origen", "temp")
            return {"tipo": "combate_iniciado", "entidades": entidades, "texto": combate(entidades), "beat_id": beat1} # Como el tema del combate se gestiona a través de la api, aquí solo devolvemos que el combate ha iniciado
    narracion = narrador(accion)
    return {"tipo": "narracion", "texto": narracion}

                

