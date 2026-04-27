import json # Para leer y escribir los JSONs del estado de la partida
import re # Para extraer JSON de bloques markdown que devuelve el LLM
from dotenv import load_dotenv # Para cargar la API key desde el .env
from langchain_openai import ChatOpenAI # El LLM que usamos para detectar intenciones
from langchain_core.messages import SystemMessage, HumanMessage # Tipos de mensaje para el LLM detector
from langchain_core.output_parsers import JsonOutputParser # Para parsear las respuestas JSON del LLM

from agentes.Narrador import narrador, narrador_inicio # El narrador principal de la partida
from agentes.director import generar_campaña, campaña_existe, cargar_campaña # Para crear y cargar la campaña
from agentes.enriquecedor import enriquecer_entidades, entidades_existen # Para generar las fichas de enemigos y NPCs
from agentes.combate import combate # El agente de combate
from agentes.creador_personaje import crear_personaje, personaje_existe # Para crear la ficha del jugador

from tools.campana import get_siguiente_beat, marcar_beat_completado # Para navegar por los beats de la campaña
from tools.inventario import add_item_to_inventory # Para añadir loot al inventario del jugador
from tools.entidades import get_info_entidad # Para consultar el estado de una entidad concreta

from config import RESUMEN_PATH, CAMPAIGN_PATH, ENTIDADES_PATH, STATS_PATH, MODEL_NAME, TEMPERATURE_LOGICA # Rutas y configuración general
from ui import (narrador_msg, combate_msg, victoria_msg, derrota_msg, # Funciones batch de la UI (siguen usándose en sitios sin streaming)
                sistema_msg, titulo_msg, prompt_jugador, prompt_input,
                narrador_msg_inicio, narrador_msg_chunk, narrador_msg_fin, # Helpers de streaming para narración estándar
                victoria_msg_inicio, victoria_msg_chunk, victoria_msg_fin, # Helpers de streaming para narración de victoria
                derrota_msg_inicio, derrota_msg_chunk, derrota_msg_fin) # Helpers de streaming para narración de derrota

_llm_detector = ChatOpenAI(model=MODEL_NAME, temperature=TEMPERATURE_LOGICA) # LLM de baja temperatura para decisiones lógicas (detectar ataques, objetivos...)
_parser_detector = JsonOutputParser() # Parser para las respuestas JSON del LLM detector


def _nueva_campaña(): # Pide datos al jugador y genera una campaña nueva desde cero
    titulo_msg("CREACIÓN DE CAMPAÑA") # Mostramos el título de la sección
    tema = prompt_input("¿Qué tipo de aventura quieres? (ej: mazmorra oscura, bosque maldito, ciudad pirata)") # Pedimos el tema de la aventura
    personaje = prompt_input("Describe tu personaje (ej: Thorin, enano guerrero)") # Pedimos la descripción del personaje

    sistema_msg("Generando tu campaña... (esto puede tardar unos segundos)") # Avisamos de que puede tardar
    campaña = generar_campaña(tema, personaje) # El director genera la campaña completa
    titulo_msg(f"¡Campaña '{campaña['titulo']}' creada!") # Mostramos el título de la campaña recién creada
    narrador_msg(f"Gancho: {campaña['gancho']}") # Mostramos el gancho argumental

    sistema_msg("Generando ficha de personaje...") # Avisamos de que vamos a crear la ficha
    stats = crear_personaje(personaje, campaña) # El creador de personaje genera la ficha a partir de la descripción y las armas disponibles
    sistema_msg(f"Personaje creado: {stats['nombre']} ({stats.get('raza', '')} {stats['clase']}) — HP: {stats['vida_max']} | AC: {stats['ac']} | Arma: {stats['arma']['nombre']}") # Mostramos un resumen de la ficha

    return campaña # Devolvemos la campaña para seguir usándola


def _limpiar_partida(): # Borra todos los archivos de la partida anterior para empezar de cero
    for path in [CAMPAIGN_PATH, ENTIDADES_PATH, STATS_PATH]: # Borramos campaña, entidades y stats
        if path.exists(): # Solo si el archivo existe, para no lanzar error
            path.unlink() # Lo borramos del disco

    RESUMEN_PATH.parent.mkdir(parents=True, exist_ok=True) # Nos aseguramos de que la carpeta data/ existe
    with open(RESUMEN_PATH, 'w', encoding='utf-8') as f: # Vaciamos el resumen (no lo borramos, solo lo dejamos en blanco)
        f.write("")


def iniciar_campaña(): # Muestra el menú de inicio y devuelve la campaña lista para jugar
    if campaña_existe(): # Si ya hay una campaña guardada, preguntamos si continuar o empezar nueva
        campaña = cargar_campaña() # Cargamos la campaña existente
        titulo_msg(f"Campaña encontrada: '{campaña.get('titulo', 'Sin título')}'") # Mostramos su título
        print("  1. Continuar partida") # Opción 1: seguir donde lo dejamos
        print("  2. Nueva campaña\n") # Opción 2: empezar desde cero
        opcion = prompt_input("Elige una opción (1/2)") # Esperamos la elección del jugador

        if opcion == "2": # Si elige nueva campaña, limpiamos todo y generamos una nueva
            _limpiar_partida() # Borramos los archivos de la partida anterior
            campaña = _nueva_campaña() # Generamos la nueva campaña
        else: # Si elige continuar, simplemente cargamos la campaña y verificamos que haya ficha de personaje
            sistema_msg("Continuando partida...") # Avisamos de que continuamos
            if not personaje_existe(): # Si no hay ficha guardada, pedimos al jugador que la regenere
                sistema_msg("No se encontró ficha de personaje.")
                desc = prompt_input("Describe tu personaje para regenerar la ficha (ej: Thorin, enano guerrero)") # Pedimos la descripción
                stats = crear_personaje(desc, campaña) # Regeneramos la ficha
                sistema_msg(f"Ficha regenerada: {stats['nombre']} ({stats.get('raza', '')} {stats['clase']})") # Confirmamos la regeneración
    else: # Si no hay campaña, creamos una nueva directamente sin menú
        campaña = _nueva_campaña()

    if not entidades_existen(): # Si no se han generado las fichas de enemigos y NPCs todavía, las generamos ahora
        sistema_msg("Generando fichas detalladas de enemigos y NPCs...") # Avisamos de que puede tardar
        enriquecer_entidades(campaña) # El enriquecedor genera las fichas completas a partir de la campaña
        sistema_msg("Fichas generadas.") # Confirmamos que se han generado

    return campaña # Devolvemos la campaña lista para usar en el bucle principal


def _beat_es_combate(): # Comprueba si el siguiente beat pendiente es de combate y lo devuelve, o None si no lo es
    raw = get_siguiente_beat.invoke({}) # Consultamos cuál es el siguiente beat
    if raw == "CAMPAÑA COMPLETADA": # Si la campaña ha terminado, no hay beat de combate
        return None

    data = json.loads(raw) # Parseamos la respuesta JSON del beat
    beat = data.get("beat", {}) # Extraemos el objeto beat

    if beat.get("tipo") in ("combate", "jefe", "climax"): # Solo consideramos combate si el tipo es de los que implican pelea
        return beat # Devolvemos el beat para que el orquestador pueda usarlo
    return None # Si no es de combate, devolvemos None


def _detectar_intento_ataque(user_input: str, resumen: str) -> bool: # Detecta si el jugador intenta atacar a alguien presente en la escena
    respuesta = _llm_detector.invoke([ # Preguntamos al LLM detector si hay intención de ataque y si hay objetivo en escena
        SystemMessage(content=(
            "Eres un árbitro de combate en un juego de rol. Tu tarea es determinar DOS cosas:\n"
            "1. ¿El jugador quiere atacar, golpear, herir o agredir físicamente a alguien?\n"
            "2. ¿El contexto narrativo reciente menciona algún personaje, criatura o entidad "
            "que pueda ser atacada (NPC, enemigo, guardia, animal, etc.)?\n\n"
            "Responde SOLO con JSON válido, sin texto extra:\n"
            "{\"quiere_atacar\": true/false, \"hay_objetivo_en_escena\": true/false}"
        )),
        HumanMessage(content=f"Contexto narrativo reciente:\n{resumen}\n\nAcción del jugador: {user_input}")
    ])
    try:
        resultado = _parser_detector.parse(respuesta.content) # Parseamos la respuesta JSON del LLM
        return bool(resultado.get("quiere_atacar", False) and resultado.get("hay_objetivo_en_escena", False)) # True solo si quiere atacar Y hay objetivo
    except Exception:
        return False # Si falla el parseo, asumimos que no hay intento de ataque


def _get_entidades_presentes() -> list: # Devuelve las entidades vivas del beat actual (enemigos y NPCs registrados en entidades.json)
    raw = get_siguiente_beat.invoke({}) # Consultamos el beat actual
    if raw == "CAMPAÑA COMPLETADA": # Si la campaña terminó, no hay entidades
        return []

    data = json.loads(raw) # Parseamos la respuesta del beat
    beat = data.get("beat", {}) # Extraemos el objeto beat
    beat_id = beat.get("id", "") # Guardamos el id del beat para filtrar entidades

    if not ENTIDADES_PATH.exists(): # Si no hay archivo de entidades todavía, devolvemos lista vacía
        return []

    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f: # Leemos todas las entidades generadas
        entidades = json.load(f)

    presentes = [] # Aquí iremos acumulando las entidades presentes en este beat

    for e in entidades.get("enemigos", []): # Filtramos los enemigos que pertenecen a este beat y están vivos
        if e.get("beat_origen") == beat_id and e.get("estado") == "vivo":
            e_copy = dict(e) # Hacemos una copia para no modificar el original
            e_copy["tipo_entidad"] = "enemigo" # Marcamos el tipo para que el sistema de combate lo sepa
            presentes.append(e_copy)

    npc_nombre = beat.get("npc") # Comprobamos si el beat tiene un NPC asociado
    if npc_nombre: # Si hay NPC, buscamos su ficha y comprobamos si está vivo
        for npc in entidades.get("npcs", []):
            if npc.get("nombre", "").lower() == npc_nombre.lower() and npc.get("estado") == "vivo":
                npc_copy = dict(npc) # Hacemos una copia del NPC para no modificar el original
                npc_copy["tipo_entidad"] = "npc" # Marcamos el tipo como NPC
                presentes.append(npc_copy)

    return presentes # Devolvemos todas las entidades vivas del beat


def _hay_entidad_atacable(user_input: str, resumen: str) -> bool: # Comprueba si hay alguien presente a quien atacar según el contexto narrativo
    respuesta = _llm_detector.invoke([ # Preguntamos al LLM si hay un objetivo razonable en la escena
        SystemMessage(content=(
            "Eres un árbitro de un juego de rol. "
            "Dado el resumen narrativo reciente y la acción del jugador, determina si "
            "hay alguna entidad (persona, criatura, monstruo) presente en la escena a la que "
            "el jugador pueda atacar razonablemente. "
            "No cuenten objetos inanimados como árboles, puertas o paredes. "
            "Responde SOLO con JSON válido, sin texto extra: "
            "{\"hay_objetivo\": true} o {\"hay_objetivo\": false}"
        )),
        HumanMessage(content=f"Resumen narrativo reciente:\n{resumen}\n\nAcción del jugador: {user_input}")
    ])
    try:
        contenido = respuesta.content # Guardamos el texto de la respuesta
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', contenido) # Por si el LLM envuelve el JSON en bloques markdown
        if match:
            contenido = match.group(1).strip() # Extraemos solo el JSON del interior del bloque
        resultado = json.loads(contenido) # Parseamos el JSON
        return bool(resultado.get("hay_objetivo", False)) # True si hay objetivo atacable
    except Exception:
        return False # Si falla el parseo, asumimos que no hay objetivo


def _generar_enemigo_narrativo(user_input: str, resumen: str) -> list: # Genera stats temporales para un enemigo que no está en entidades.json y lo inserta
    llm_gen = ChatOpenAI(model=MODEL_NAME, temperature=0.3) # LLM con temperatura baja para generar stats coherentes
    respuesta = llm_gen.invoke([ # Pedimos al LLM que genere la ficha del enemigo basándose en el contexto
        SystemMessage(content=(
            "Eres un generador de stats de enemigos para D&D. "
            "Basándote en el contexto narrativo, genera stats para el o los enemigos "
            "que el jugador quiere atacar. "
            "Responde SOLO con JSON válido (lista), sin texto extra:\n"
            "[\n"
            "  {\n"
            '    "id": "temp_<nombre_sin_espacios>_1",\n'
            '    "nombre": "<nombre legible>",\n'
            '    "tipo": "humano",\n'
            '    "beat_origen": "temp",\n'
            '    "estado": "vivo",\n'
            '    "vida_max": <10-20>,\n'
            '    "vida_actual": <igual a vida_max>,\n'
            '    "ac": <10-13>,\n'
            '    "dado_daño": "1d6",\n'
            '    "xp": 50,\n'
            '    "atributos": {"fue": 2, "des": 2, "con": 1, "int": 1, "sab": 1, "car": 1},\n'
            '    "arma": "daga",\n'
            '    "descripcion": "<descripción breve>"\n'
            "  }\n"
            "]\n"
            "Genera solo los enemigos que el jugador menciona atacar directamente. "
            "Ajusta los stats al tipo de personaje que aparece en el contexto."
        )),
        HumanMessage(content=f"Contexto narrativo reciente:\n{resumen}\n\nAcción del jugador: {user_input}")
    ])
    try:
        contenido = respuesta.content # Guardamos el texto de la respuesta
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', contenido) # Por si el LLM envuelve el JSON en bloques markdown
        if match:
            contenido = match.group(1).strip() # Extraemos el JSON del bloque markdown

        enemigos = json.loads(contenido) # Parseamos la lista de enemigos generados
        if not isinstance(enemigos, list): # Si el LLM no devuelve una lista, algo fue mal
            return []

        with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f: # Leemos el archivo de entidades existente para insertar los nuevos
            entidades = json.load(f)

        ids_existentes = {e["id"] for e in entidades.get("enemigos", [])} # Set de ids ya registrados para evitar duplicados
        nuevos = [] # Aquí acumulamos los enemigos que sí vamos a insertar

        for e in enemigos: # Recorremos los enemigos generados por el LLM
            if e.get("id") and e["id"] not in ids_existentes: # Solo insertamos si tiene id y no es duplicado
                entidades["enemigos"].append(e) # Lo añadimos a la lista de enemigos del archivo
                e_con_tipo = dict(e) # Hacemos una copia para añadir el tipo_entidad sin tocar el original
                e_con_tipo["tipo_entidad"] = "enemigo" # Marcamos el tipo para el sistema de combate
                nuevos.append(e_con_tipo) # Lo añadimos a la lista de nuevos que vamos a devolver

        with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f: # Guardamos las entidades actualizadas en el archivo
            json.dump(entidades, f, indent=2, ensure_ascii=False)

        return nuevos # Devolvemos solo los enemigos recién insertados

    except Exception as e: # Si algo falla, lo mostramos en modo debug y devolvemos lista vacía
        sistema_msg(f"[DEBUG] Excepción en _generar_enemigo_narrativo: {e}")
        return []


def _recoger_loot(entidades: list) -> list: # Recoge el loot de las entidades derrotadas y lo añade al inventario del jugador
    items_recogidos = [] # Aquí acumulamos todos los items que recojamos
    for e in entidades: # Recorremos todas las entidades del combate
        info_raw = get_info_entidad.invoke({"entidad_id": e["id"]}) # Consultamos el estado actualizado de la entidad (puede tener loot)
        try:
            info = json.loads(info_raw) # Parseamos la info de la entidad
        except (json.JSONDecodeError, TypeError):
            continue # Si no se puede parsear, pasamos a la siguiente entidad

        if info.get("estado") != "muerto": # Solo recogemos loot de los que están muertos
            continue

        for item in info.get("loot", []): # Recorremos el loot de la entidad muerta
            add_item_to_inventory.invoke({"item_json": json.dumps(item, ensure_ascii=False)}) # Añadimos cada item al inventario
            items_recogidos.append(item) # Lo añadimos a la lista de items recogidos

    if items_recogidos: # Si hemos recogido algo, lo mostramos al jugador
        nombres = ", ".join(i["nombre"] for i in items_recogidos) # Juntamos los nombres en un string
        sistema_msg(f"Loot recogido: {nombres}") # Mostramos los items recogidos

    return items_recogidos # Devolvemos la lista de items recogidos


def main(): # Bucle principal del juego
    load_dotenv() # Cargamos las variables de entorno (API key, etc.)

    campaña = iniciar_campaña() # Generamos o cargamos la campaña antes de empezar a jugar

    while True: # Bucle principal de la partida
        beat_combate = _beat_es_combate() # Comprobamos si toca combate antes de pedir input al jugador
        if beat_combate: # Si el siguiente beat es de combate, lo resolvemos sin esperar input
            narrador_msg_inicio() # El narrador introduce el combate (streaming)
            narrador(
                f"[SISTEMA] El jugador llega al momento: {beat_combate['descripcion']}. Narra la aparición de los enemigos y la tensión del momento.",
                on_chunk=narrador_msg_chunk
            )
            narrador_msg_fin()

            entidades_beat = _get_entidades_presentes() # Obtenemos las entidades del beat
            for e in entidades_beat: # Marcamos todas como enemigos para el sistema de combate
                e["tipo_entidad"] = "enemigo"
            resultado = combate(entidades_beat) # Lanzamos el combate con las entidades del beat

            if resultado == "victoria": # Si el jugador ganó el combate
                marcar_beat_completado.invoke({"beat_id": beat_combate["id"]}) # Marcamos el beat como superado
                loot = _recoger_loot(entidades_beat) # Recogemos el loot de los enemigos muertos
                loot_fragment = f" Ha recogido: {', '.join(i['nombre'] for i in loot)}." if loot else "" # Texto del loot para el narrador
                victoria_msg_inicio() # Mostramos la narración de victoria (streaming)
                narrador(
                    f"[SISTEMA] El jugador ha ganado el combate en: {beat_combate['descripcion']}.{loot_fragment} Narra las consecuencias de la victoria y guía hacia lo que viene después.",
                    on_chunk=victoria_msg_chunk
                )
                victoria_msg_fin()
            elif resultado == "resolucion": # Si el jugador resolvió el combate sin matar a todos (huida, negociación...)
                marcar_beat_completado.invoke({"beat_id": beat_combate["id"]}) # El beat también queda superado
                loot = _recoger_loot(entidades_beat) # Recogemos loot de los que sí murieron durante el combate
                loot_fragment = f" Ha recogido: {', '.join(i['nombre'] for i in loot)}." if loot else "" # Texto del loot
                narrador_msg_inicio() # Mostramos la narración del desenlace (streaming)
                narrador(
                    f"[SISTEMA] El jugador ha resuelto el combate en: {beat_combate['descripcion']} de forma narrativa (huida, negociación, intimidación, etc.) sin matar a todos los enemigos.{loot_fragment} Narra el desenlace y guía hacia lo que viene después.",
                    on_chunk=narrador_msg_chunk
                )
                narrador_msg_fin()
            else: # Si el jugador fue derrotado
                derrota_msg_inicio() # Mostramos la narración de derrota (streaming)
                narrador(
                    f"[SISTEMA] El jugador ha sido derrotado en: {beat_combate['descripcion']}. Narra su caída.",
                    on_chunk=derrota_msg_chunk
                )
                derrota_msg_fin()
                break # Terminamos la partida
            continue # Volvemos al inicio del bucle para comprobar el siguiente beat

        resumen = RESUMEN_PATH.read_text(encoding='utf-8').strip() if RESUMEN_PATH.exists() else "" # Leemos el resumen actual de la partida

        if resumen: # Si ya hay resumen, la partida está en marcha y pedimos la siguiente acción
            user_input = prompt_jugador() # Pedimos la acción al jugador
            if user_input.lower() == "salir": # Si escribe "salir", terminamos la partida
                break

            if _detectar_intento_ataque(user_input, resumen): # Comprobamos si el jugador quiere atacar a alguien
                entidades = _get_entidades_presentes() # Primero buscamos entidades registradas en el beat actual

                if not entidades and _hay_entidad_atacable(user_input, resumen): # Si no hay entidades registradas pero el LLM detecta que hay alguien presente...
                    entidades = _generar_enemigo_narrativo(user_input, resumen) # ...generamos una ficha temporal para ese enemigo narrativo

                if entidades: # Si hay entidades con las que combatir, iniciamos el combate
                    resultado = combate(entidades) # Lanzamos el combate

                    nombres_derrotados = ", ".join(e['nombre'] for e in entidades) # Juntamos los nombres de los enemigos para el resumen
                    if resultado == "victoria": # Texto del resultado para el resumen
                        cierre = "venció, eliminándoles."
                    elif resultado == "resolucion":
                        cierre = "resolvió el combate sin matarles (huida, negociación o similar)."
                    else:
                        cierre = "fue derrotado."
                    resumen_combate = f"El jugador inició un combate inesperado contra {nombres_derrotados} y {cierre}" # Frase de resumen del combate
                    RESUMEN_PATH.parent.mkdir(parents=True, exist_ok=True) # Nos aseguramos de que la carpeta existe
                    with open(RESUMEN_PATH, 'a', encoding='utf-8') as f: # Añadimos el resumen del combate al archivo
                        f.write(resumen_combate + "\n")

                    if resultado == "derrota": # Si el jugador fue derrotado, terminamos la partida
                        break

                    if resultado == "resolucion": # Si se resolvió narrativamente, narramos el desenlace y continuamos
                        loot = _recoger_loot(entidades) # Recogemos loot de los que murieron
                        loot_fragment = f" Ha recogido: {', '.join(i['nombre'] for i in loot)}." if loot else ""
                        narrador_msg_inicio() # Streaming
                        narrador(
                            f"[SISTEMA] El combate contra {nombres_derrotados} ha terminado de forma narrativa (huida, negociación, intimidación, etc.) sin matarles a todos.{loot_fragment} "
                            f"Narra el desenlace y continúa la historia.",
                            on_chunk=narrador_msg_chunk
                        )
                        narrador_msg_fin()
                        continue # Volvemos al inicio del bucle

                    loot = _recoger_loot(entidades) # Si fue victoria, recogemos el loot
                    loot_fragment = f" Ha recogido: {', '.join(i['nombre'] for i in loot)}." if loot else ""
                    narrador_msg_inicio() # Narramos las consecuencias de la victoria (streaming)
                    narrador(
                        f"[SISTEMA] El jugador acaba de derrotar en combate a: {nombres_derrotados}. "
                        f"Esas criaturas/personajes han muerto y ya no están presentes.{loot_fragment} "
                        f"Narra las consecuencias de la victoria y continúa la historia.",
                        on_chunk=narrador_msg_chunk
                    )
                    narrador_msg_fin()
                    continue # Volvemos al inicio del bucle

            narrador_msg_inicio() # Si no hay combate, el narrador procesa la acción normalmente (streaming)
            narrador(user_input, on_chunk=narrador_msg_chunk)
            narrador_msg_fin()

        else: # Si no hay resumen todavía, es el inicio de la partida
            narrador_msg_inicio() # El narrador genera la narración de apertura con el contexto de la campaña (streaming)
            narrador_inicio(campaña, on_chunk=narrador_msg_chunk)
            narrador_msg_fin()


main() # Arrancamos el juego
