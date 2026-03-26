import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from tools.entidades import dañar_enemigo, dañar_npc, get_info_entidad
from tools.dados import tirar_d20, tirar_dado
from tools.inventario import get_armas, verificar_arma_en_accion
from config import STATS_PATH, COMBATE_PROMPT_PATH, MODEL_NAME # Las rutas alos ficheros de stats, prompt de comabte y el modelo de ChatGPT
from ui import combate_msg, enemigo_msg, estado_combate, victoria_msg, derrota_msg, prompt_jugador, sistema_msg

load_dotenv()

with open(COMBATE_PROMPT_PATH, 'r', encoding='utf-8') as f: # Agregamos el prompt de combate
    system_prompt_combate = f.read().strip()

llm = ChatOpenAI(model=MODEL_NAME, temperature=0.9)
llm_evaluar = ChatOpenAI(model=MODEL_NAME, temperature=0.3)
parser = JsonOutputParser() # Sirve para, más adelante, evaluar la acción del jugador y obtener una respuesta estructurada


def _modificador(valor: int) -> int: # Calcula el modificador de características de D&D
    return (valor - 10) // 2


def _cargar_jugador() -> dict: # Carga la ficha del jugador
    if not STATS_PATH.exists(): # Si no existe un jugador creado, devuelve vacío
        return {}
    with open(STATS_PATH, 'r', encoding='utf-8') as f: # Si sí existe, lo devuelve
        return json.load(f)


def _guardar_jugador(jugador: dict): # Actualiza la ficha del jugador con los nuevos datos después de un combate por ejemplo
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(jugador, f, indent=2, ensure_ascii=False)


def _narrar(contexto: str) -> str: # Narra lo que está sucediendo en el combate. Le pasamos el contexto actual (resumen)
    respuesta = llm.invoke([
        SystemMessage(content=system_prompt_combate + "\n\nMODO: NARRAR"), # Le pasamos el prompt del combate junto al flag que inicia el modo de narración
        HumanMessage(content=contexto)
    ])
    return respuesta.content


def _evaluar_accion(accion: str, contexto_combate: str) -> dict: # Comprueba si la acción que quiere ejecutar el usuario es viable en esta circunstancia
    # Si el NPC que hay delante es un orco y el jugador en el inventario tiene una espada, y el usuario quiere pegarle un tiro a un dragón, lo declarará como no viable porque no tiene sentido
    respuesta = llm_evaluar.invoke([
        SystemMessage(content=system_prompt_combate + "\n\nMODO: EVALUAR ACCIÓN"),
        HumanMessage(content=f"Contexto del combate:\n{contexto_combate}\n\nAcción del jugador: {accion}") # Le pasamos el contexto de la partida y la acción que quiere ejecutar el usuario
    ])
    try:
        return parser.parse(respuesta.content) # Parseamos la respuesta de la IA y la estructuramos para generar una resolución a la acción del usuario
    except Exception:
        return {"viable": False, "razon": "No se pudo interpretar la acción"}


def _get_vivos(entidades: list) -> list:
    # Comprueba si las entidades presentes en el combate siguen vivas.
    vivos = []
    for e in entidades:
        info_raw = get_info_entidad.invoke({"entidad_id": e["id"]}) # Llama a la herramienta para saber las stats de las entidades actualizadas, ya que las que tiene en memoria son de antes del combate
        try:
            info = json.loads(info_raw)
            if info.get("estado") == "vivo": #Comprueba qué entidades presentes siguen vivas y las devuelve
                info["tipo_entidad"] = e.get("tipo_entidad", "enemigo")
                vivos.append(info)
        except (json.JSONDecodeError, TypeError):
            pass
    return vivos


def _mostrar_estado(jugador: dict, entidades: list): # Muestra el estado actual del jugador y del/los enemigo/s
    vivos = _get_vivos(entidades)
    enemigos_str = ", ".join(
        f"{e['nombre']} ({e['vida_actual']}/{e['vida_max']})" for e in vivos
    )
    estado_combate(jugador['vida_actual'], jugador['vida_max'], enemigos_str) # Lo pone bonito para la terminal


def combate_out(entidades_presentes: list) -> str:
    """
    """
    #Función principal para gestionar un combate fuera del beat de combate, iniciado por el jugador
    jugador = _cargar_jugador() # Cargamos la ficha de stats del jugador

    if not entidades_presentes: # Si no hay entidades presentes, devuelve una victoria
        return "victoria"

    arma_turno = None  # Arma elegida por el jugador, persiste entre turnos

    # Si sí hay entidades presentes, primero guardamos el nombre, el AC y la vida actual de cada entidad presente
    nombres = ", ".join(
        f"{e['nombre']} (AC:{e.get('ac', 10)}, HP:{e.get('vida_actual', '?')})"
        for e in entidades_presentes
    )

    arma_jugador = jugador.get("arma", {}).get("nombre", "sus puños") # Obtenemos el arma del jugador, si no encuentra un arma, lo asigna como {}, y si no hay nombre para cualquier cosa que pueda tener el usuario, se declara que el usuario utiliza sus puños
    combate_msg(_narrar(
        f"El jugador ({jugador['nombre']}, armado con {arma_jugador}) inicia un ataque inesperado contra: {nombres}. Este primer ataque NO es certero, por lo que narra cómo el jugador ({jugador['nombre']}) falla el ataque o {nombres} esquivan/bloquean el ataque"
        f"Describe cómo irrumpe el combate de forma brusca e imprevista."
    )) # Mostramos esta primera narración del combate con colores para que se vean bien en la terminal
    _mostrar_estado(jugador, entidades_presentes)

    while True:

        # EMPIEZA EL TURNO CON EL JUGADOR, PORQUE ES EL QUE INICIA EL COMBATE
        accion = prompt_jugador() # El jugador escribe su acción con colores

        if not accion: # Si el usuario no escribe nada, se le vuelve a pedir que escriba una acción
            continue

        vivos = _get_vivos(entidades_presentes) # Pedimos todas las entidades vivas en la escena actualizadas, quitando al usuario

        if not vivos: # Si no quedan entidades vivas, se termina el combate
            break

        # Comprueba si el arma que intenta utilizar el usuario está en el inventario

        armas_inv = get_armas(jugador) # Comprueba que hay armas en el inventario
        if armas_inv:
            verificacion = verificar_arma_en_accion(accion, armas_inv) # Verifica si el arma que intenta utilizar, está en el inventario
            if verificacion["estado"] == "no_en_inventario": # Si el arma que intenta utilizar el usuario no está en el inventario, se narra que intenta atacar con algo que no tiene
                nombres_armas = ", ".join(a["nombre"] for a in armas_inv)
                combate_msg(_narrar(
                    f"El jugador intenta usar '{verificacion['nombre']}' pero no lo tiene. "
                    f"Sus armas son: {nombres_armas}. Narra que no tiene esa arma."
                ))
                continue # Se vuelve a preguntar qué quiere hacer
            elif verificacion["estado"] == "encontrada": # Si el arma que intenta utilizar el usuario está en el inventario, se almacena
                arma_turno = verificacion["arma"]
                jugador["arma"] = arma_turno

        # Construimo el contexto con el arma seleccionada
        arma_actual = arma_turno or jugador.get("arma", {})
        contexto = (
            f"Jugador: {jugador['nombre']} ({jugador.get('clase', '?')}), "
            f"Arma: {arma_actual.get('nombre', 'sus puños')} (dado: {arma_actual.get('dado_daño', '1d6')}), "
            f"Atributos: {json.dumps(jugador.get('atributos', {}))}\n"
            f"Entidades presentes (vivas): {json.dumps(vivos, ensure_ascii=False)}"
        )
        '''
        Al contexto del combate le pasamos la siguiente información:
        - Las stats del jugador: nombre, clase, arma elegida, el dado necesario para esta arma y sus atributos
        - Las entidades presentes vivas en el combate
        '''

        evaluacion = _evaluar_accion(accion, contexto) # Evaluamos si la acción del jugador es viable

        if not evaluacion.get("viable", False): # Explicamos por qué no es viable
            razon = evaluacion.get("razon", "Eso no es posible aquí.")
            combate_msg(_narrar(f"El jugador intenta: '{accion}'. No es viable: {razon}"))
            continue

        tipo = evaluacion.get("tipo", "accion")

        # Si el usuario decide atacar, pero no ha especificado con qué arma se pide ahora
        '''
        Estructura de la respuesta de la IA a la acción del combate del jugador:
        - Usuario: Ataco con mi espada
        - IA: Procesa que quiere atacar y lo quiere hacer con su espada (Busca arma, procesa si es viable)
        
        - Usuario: Ataco
        - IA: Procesa que quiere atacar, pero no sabe con qué quiere atacar: ¿Qué arma quieres escoger para el ataque?
        - Usuario: Mi espada
        - IA: Procesa que quiere atacar y lo quiere hacer con su espada (Busca arma, procesa si es viable)
        '''
        if tipo == "ataque" and armas_inv and arma_turno is None:
            nombres_armas = ", ".join(a["nombre"] for a in armas_inv)
            sistema_msg(f"¿Con qué arma atacas? Tienes: {nombres_armas}")
            eleccion = prompt_jugador()
            v2 = verificar_arma_en_accion(eleccion, armas_inv)
            if v2["estado"] == "encontrada": # Si encuentra el arma la almacena
                arma_turno = v2["arma"]
                jugador["arma"] = arma_turno 
            else:
                combate_msg(f"No tienes esa arma. Armas disponibles: {nombres_armas}")
                continue

        # Si hay arma elegida, sobreescribimos el dado de daño que sugirió la IA con el dado real del inventario
        if arma_turno:
            evaluacion["dado_daño"] = arma_turno.get("dado_daño", evaluacion.get("dado_daño", "1d6"))

        atributo = evaluacion.get("atributo", "fue") # Se comprueba qué atributo se asigna al ataque, si no se sabe, se le atribuye fuerza
        dc = evaluacion.get("dc", 12) # Se comprueba la dificultad para atacar, si no, se asigna 12 por defecto
        mod = _modificador(jugador.get("atributos", {}).get(atributo, 0))

        tirada = tirar_d20.invoke({}) # Invocamos al dado de 20 caras para saber si golpea o no
        critico = (tirada == 20 and tipo == "ataque") # Si saca la cara 20 en un ataque hace un crítico
        total = tirada + mod # El ataque final es el resultado del daño del dado junto al modificador de daño

        if critico or total >= dc:# Si el ataque acierta, se calcula cuánto daño hace el jugador
            dado_daño = evaluacion.get("dado_daño")# Comprobamos si se puede hacer daño
            objetivo_id = evaluacion.get("objetivo")# Buscamos el id del objetivo en la escena, tanto enemigo como NPC

            if dado_daño: # Si se puede hacer daño, tiramos el dado de daño correspondiente al arma que se esté empleando
                daño = tirar_dado.invoke({"dado": dado_daño}) + mod # Le añadimos el modificador de daño
                if critico: # Si ha sido crítico, tiramos otro dado de daño para añadirlo al total de daño realizado
                    daño += tirar_dado.invoke({"dado": dado_daño})
                daño = max(1, daño)

                if objetivo_id: 
                    entidad_objetivo = next(
                        (e for e in entidades_presentes if e["id"] == objetivo_id), None # Si existe un objetivo en la escena, se busca dentro de toda la lista de personajes de la historia a ver cuál coincide con ese ID. Se tiene que hacer así, porque es la IA la que interpreta si hay un enemigo en la escena o no, por lo que hay que comprobarlo
                    )
                    tipo_entidad = entidad_objetivo.get("tipo_entidad", "enemigo") if entidad_objetivo else "enemigo"
                    #Comprueba el tipo de entidad que es: NPC o enemigo, si no lo sabe, lo cataloga como enemigo
                    if tipo_entidad == "npc":
                        resultado = json.loads(dañar_npc.invoke({"npc_id": objetivo_id, "daño": daño}))
                    else:
                        resultado = json.loads(dañar_enemigo.invoke({"enemigo_id": objetivo_id, "daño": daño}))
                    msg_daño = resultado["mensaje"]
                else:
                    # Si la IA no identificó un objetivo concreto, el daño se aplica a todas las entidades vivas
                    msg_daño = ""
                    for e in vivos:
                        if e.get("tipo_entidad") == "npc":
                            resultado = json.loads(dañar_npc.invoke({"npc_id": e["id"], "daño": daño}))
                        else:
                            resultado = json.loads(dañar_enemigo.invoke({"enemigo_id": e["id"], "daño": daño}))
                        msg_daño += resultado["mensaje"] + " "

                combate_msg(_narrar( # Narramos el resultado del ataque con todos los datos para que la IA pueda describir la escena
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. "
                    f"{'¡CRÍTICO! ' if critico else ''}ÉXITO. Daño: {daño}. {msg_daño}"
                ))
            else:
                # Si el ataque no hace daño directo (ej: empujar, cegar, derrumbar), se narra el efecto especial
                efecto = evaluacion.get("efecto_exito", "")
                combate_msg(_narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. ÉXITO. Efecto: {efecto}"
                ))
        else:
            # Si el total de la tirada no supera la DC, el ataque falla y se narra el efecto de fallo
            efecto = evaluacion.get("efecto_fallo", "")
            combate_msg(_narrar(
                f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                f"{tirada}+{mod}={total} vs DC {dc}. FALLO. Efecto: {efecto}"
            ))

        # Comprobamos si quedan entidades vivas tras el turno del jugador
        vivos_actual = _get_vivos(entidades_presentes)
        if not vivos_actual: # Si no queda ninguna, el jugador ha ganado
            victoria_msg(_narrar(
                f"Todas las entidades han caído. El jugador triunfa en este enfrentamiento inesperado."
            ))
            return "victoria"

        # Turno de cada entidad viva: cada una intenta atacar al jugador por separado
        for e in vivos_actual:
            info_raw = get_info_entidad.invoke({"entidad_id": e["id"]}) # Obtenemos las stats actualizadas de la entidad
            try:
                info = json.loads(info_raw)
            except (json.JSONDecodeError, TypeError):
                continue

            mod_fue = _modificador(info.get("atributos", {}).get("fue", 2)) # Modificador de fuerza de la entidad
            tirada_enemigo = tirar_d20.invoke({}) # La entidad tira su d20
            total_enemigo = tirada_enemigo + mod_fue # Total = tirada + modificador de fuerza

            if total_enemigo >= jugador["ac"]: # Si supera la AC del jugador, el ataque acierta
                daño_enemigo = tirar_dado.invoke({"dado": info.get("dado_daño", "1d4")}) + mod_fue # Tiramos el dado de daño de la entidad
                daño_enemigo = max(1, daño_enemigo) # El daño mínimo es 1
                jugador["vida_actual"] = max(0, jugador["vida_actual"] - daño_enemigo) # Restamos el daño a la vida del jugador, mínimo 0
                _guardar_jugador(jugador) # Guardamos la ficha actualizada del jugador

                enemigo_msg(info['nombre'], _narrar(
                    f"{info['nombre']} contraataca al jugador con {info.get('arma', 'sus manos')}. "
                    f"Tirada: {tirada_enemigo}+{mod_fue}={total_enemigo} vs AC {jugador['ac']}. "
                    f"ACIERTA. Daño: {daño_enemigo}. "
                    f"Vida jugador: {jugador['vida_actual']}/{jugador['vida_max']}"
                ))
            else: # Si no supera la AC, el ataque falla
                enemigo_msg(info['nombre'], _narrar(
                    f"{info['nombre']} intenta contraatacar al jugador. "
                    f"Tirada: {tirada_enemigo}+{mod_fue}={total_enemigo} vs AC {jugador['ac']}. FALLA."
                ))

        # Comprobamos si el jugador sigue vivo tras los ataques de las entidades
        if jugador["vida_actual"] <= 0: # Si la vida del jugador llega a 0, ha sido derrotado
            derrota_msg(_narrar(
                f"{jugador['nombre']} cae con {jugador['vida_actual']} HP en un enfrentamiento imprevisto. "
                f"Narra su caída."
            ))
            return "derrota"

        _mostrar_estado(jugador, entidades_presentes) # Mostramos el estado actualizado al inicio del siguiente turno
