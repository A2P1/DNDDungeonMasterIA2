import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent)) # Añadimos la raíz del proyecto al path para que los imports funcionen

import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from tools.entidades import dañar_enemigo, dañar_npc, get_info_entidad, get_estado_combate
from tools.dados import tirar_d20, tirar_dado
from tools.inventario import get_armas, verificar_arma_en_accion, usar_item
from config import STATS_PATH, COMBATE_PROMPT_PATH, MODEL_NAME
from ui import combate_msg, enemigo_msg, estado_combate, victoria_msg, derrota_msg, prompt_jugador, sistema_msg

load_dotenv() # Cargamos las variables de entorno (.env) para tener acceso a la API key

with open(COMBATE_PROMPT_PATH, 'r', encoding='utf-8') as f: # Leemos el prompt de combate desde el archivo de texto
    system_prompt_combate = f.read().strip()

llm = ChatOpenAI(model=MODEL_NAME, temperature=0.9) # LLM para narrar, temperatura alta para respuestas más creativas
llm_evaluar = ChatOpenAI(model=MODEL_NAME, temperature=0.3) # LLM para evaluar acciones, temperatura baja para respuestas más consistentes
parser = JsonOutputParser() # Parseador para convertir la respuesta del LLM a un dict de Python


def _modificador(valor: int) -> int: # El atributo (0-5) se usa directamente como modificador (Cosmere RPG)
    return valor


def _cargar_jugador() -> dict: # Lee el stats.json y devuelve la ficha del jugador como dict
    if not STATS_PATH.exists(): # Si no existe el archivo, devolvemos un dict vacío
        return {}
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _guardar_jugador(jugador: dict): # Sobreescribe el stats.json con los datos actualizados del jugador
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(jugador, f, indent=2, ensure_ascii=False)


def _narrar(contexto: str) -> str: # Le pasa el contexto al LLM en modo NARRAR y devuelve el texto generado
    respuesta = llm.invoke([
        SystemMessage(content=system_prompt_combate + "\n\nMODO: NARRAR"), # Le decimos al LLM que solo tiene que narrar
        HumanMessage(content=contexto) # El contexto con lo que ha pasado en el turno
    ])
    return respuesta.content


def _evaluar_accion(accion: str, contexto_combate: str) -> dict: # Le pasa la acción del jugador al LLM en modo EVALUAR y devuelve un dict con el resultado
    respuesta = llm_evaluar.invoke([
        SystemMessage(content=system_prompt_combate + "\n\nMODO: EVALUAR ACCIÓN"), # Le decimos al LLM que tiene que evaluar la acción
        HumanMessage(content=f"Contexto del combate:\n{contexto_combate}\n\nAcción del jugador: {accion}")
    ])
    try:
        return parser.parse(respuesta.content) # Intentamos parsear la respuesta como JSON
    except Exception:
        return {"viable": False, "razon": "No se pudo interpretar la acción"} # Si falla el parseo devolvemos acción no viable


def _get_vivos(entidades: list) -> list: # Recorre la lista de entidades y devuelve solo las que siguen vivas según entidades.json
    vivos = []
    for e in entidades:
        info_raw = get_info_entidad.invoke({"entidad_id": e["id"]}) # Consultamos el estado actualizado de cada entidad
        try:
            info = json.loads(info_raw)
            if info.get("estado") == "vivo": # Solo añadimos las que siguen vivas
                info["tipo_entidad"] = e.get("tipo_entidad", "enemigo") # Conservamos si es enemigo o NPC
                vivos.append(info)
        except (json.JSONDecodeError, TypeError): # Si falla el parseo ignoramos esa entidad
            pass
    return vivos


def _mostrar_estado(jugador: dict, entidades: list): # Imprime en la terminal la vida del jugador y el estado de los enemigos
    vivos = _get_vivos(entidades) # Obtenemos las entidades vivas actualizadas
    enemigos_str = ", ".join(
        f"{e['nombre']} ({e['vida_actual']}/{e['vida_max']})" for e in vivos # Formateamos cada enemigo como "Nombre (vida_actual/vida_max)"
    )
    estado_combate(jugador['vida_actual'], jugador['vida_max'], enemigos_str) # Lo mostramos con colores en la terminal


# ── API ──────────────────────────────────────────────────────────────────────

def _respuesta_turno(jugador: dict, estado: dict, narracion: str, resultado) -> dict: # Construye el dict que devuelve la API al frontend con el estado del turno
    return {
        "narracion": narracion, # Texto narrado del turno
        "jugador_vida": jugador["vida_actual"],
        "jugador_vida_max": jugador["vida_max"],
        "entidades_vivas": estado.get("enemigos_vivos", []), # Lista de enemigos que siguen vivos
        "combate_terminado": estado.get("combate_terminado", False),
        "resultado": resultado # "victoria", "derrota" o None si el combate sigue
    }


def procesar_turno(beat_id: str, accion: str) -> dict: # Procesa un turno completo de combate para la API y devuelve el estado actualizado
    jugador = _cargar_jugador()
    narracion = [] # Lista donde vamos acumulando los textos narrados del turno

    estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id})) # Consultamos el estado actual del combate
    enemigos_vivos = estado.get("enemigos_vivos", [])

    if not enemigos_vivos: # Si no quedan enemigos, victoria directa sin procesar nada
        return _respuesta_turno(jugador, estado, "No quedan enemigos.", "victoria")

    armas_inv = get_armas(jugador) # Obtenemos las armas del inventario del jugador
    if armas_inv:
        verificacion = verificar_arma_en_accion(accion, armas_inv) # Comprobamos si menciona un arma en su acción
        if verificacion["estado"] == "no_en_inventario": # Si menciona un arma que no tiene, lo narramos y paramos
            nombres_armas = ", ".join(a["nombre"] for a in armas_inv)
            texto = _narrar(
                f"El jugador intenta usar '{verificacion['nombre']}' pero no lo tiene. "
                f"Sus armas son: {nombres_armas}. Narra que no tiene esa arma."
            )
            return _respuesta_turno(jugador, estado, texto, None)
        elif verificacion["estado"] == "encontrada": # Si menciona un arma válida, la guardamos como arma activa
            jugador["arma"] = verificacion["arma"]
            _guardar_jugador(jugador) # Persistimos el cambio de arma para que no se pierda si no hay daño en este turno

    arma_actual = jugador.get("arma", {}) # Cogemos el arma activa, si no tiene ninguna usamos un dict vacío
    consumibles = [i for i in jugador.get("inventario", []) if i.get("tipo") == "consumible"] # Items consumibles disponibles
    contexto = ( # Construimos el contexto que le pasaremos al LLM para que evalúe la acción
        f"Jugador: {jugador['nombre']} ({jugador.get('clase', '?')}), "
        f"Arma: {arma_actual.get('nombre', 'sus puños')} (dado: {arma_actual.get('dado_daño', '1d6')}), "
        f"Atributos: {json.dumps(jugador.get('atributos', {}))}\n"
        f"Consumibles disponibles: {json.dumps(consumibles, ensure_ascii=False)}\n"
        f"Enemigos vivos: {json.dumps(enemigos_vivos, ensure_ascii=False)}"
    )
    evaluacion = _evaluar_accion(accion, contexto) # El LLM decide si la acción es viable y cómo resolverla

    if not evaluacion.get("viable", False): # Si la acción no es viable, narramos el motivo y devolvemos sin procesar el turno
        razon = evaluacion.get("razon", "Eso no es posible aquí.")
        texto = _narrar(f"El jugador intenta: '{accion}'. No es viable: {razon}")
        return _respuesta_turno(jugador, estado, texto, None)

    tipo = evaluacion.get("tipo", "accion") # "ataque" o "accion" (algo que no hace daño directo)
    atributo = evaluacion.get("atributo", "fue") # Atributo que se usa para la tirada (fue, des, con...)
    dc = evaluacion.get("dc", 12) # Dificultad que hay que superar con la tirada
    mod = _modificador(jugador.get("atributos", {}).get(atributo, 0)) # Modificador del atributo del jugador

    ventaja_enemigos = False # Se activa si el jugador saca pifia: los enemigos atacarán ese turno con ventaja

    # Si el jugador usa un item consumible, se resuelve sin tirada y consume el turno (los enemigos atacan igual más abajo)
    item_name = evaluacion.get("usa_item")
    if item_name:
        resultado_item = usar_item.invoke({"nombre_item": item_name})
        jugador = _cargar_jugador() # Recargamos para reflejar cambios en HP e inventario
        narracion.append(_narrar(
            f"El jugador usa '{item_name}'. Resultado: {resultado_item}. Narra el uso del item con color."
        ))
    else:
        tirada = tirar_d20.invoke({}) # Tiramos el d20
        critico = (tirada == 20 and tipo == "ataque") # Nat 20 en ataque = crítico
        pifia = (tirada == 1) # Nat 1 = pifia, fallo automático con complicación
        total = tirada + mod # Total final de la tirada

        if pifia: # Si saca un 1, fallo automático independientemente del modificador
            ventaja_enemigos = True # El jugador queda expuesto: los enemigos atacan con ventaja este turno
            narracion.append(_narrar(
                f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                f"NAT 1. ¡PIFIA! El ataque falla estrepitosamente y el jugador queda expuesto. "
                f"Narra una complicación: el arma se atasca, el jugador tropieza, "
                f"se golpea a sí mismo o queda expuesto."
            ))
        elif critico or total >= dc: # Si saca 20 o supera la DC, el ataque acierta
            if evaluacion.get("termina_combate"): # La acción resuelve el combate sin victoria ni derrota
                motivo = evaluacion.get("motivo_fin", "el combate termina por una resolución narrativa")
                texto = _narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. ÉXITO. "
                    f"El combate termina: {motivo}. Narra el desenlace con tensión."
                )
                return _respuesta_turno(jugador, estado, texto, "resolucion")

            dado_daño = evaluacion.get("dado_daño") # Dado de daño del arma (ej: "1d8")
            if dado_daño: # Si hay daño que aplicar
                if critico: # Crítico: daño máximo posible (todos los dados al máximo) + modificador
                    partes = dado_daño.lower().split("d") # Separamos "1d8" en ["1", "8"]
                    cantidad = int(partes[0]) # Número de dados
                    caras = int(partes[1]) # Caras de cada dado
                    daño = (cantidad * caras) + mod # Máximo posible + modificador
                else:
                    daño = tirar_dado.invoke({"dado": dado_daño}) + mod # Tirada normal + modificador
                daño = max(1, daño) # El daño mínimo siempre es 1

                objetivo_id = evaluacion.get("objetivo") # ID de la entidad a la que ataca
                if not objetivo_id and enemigos_vivos: # Si no hay objetivo concreto, atacamos solo al primer enemigo vivo (no cleave AoE)
                    objetivo_id = enemigos_vivos[0]["id"]
                if objetivo_id:
                    resultado_daño = json.loads(dañar_enemigo.invoke({"enemigo_id": objetivo_id, "daño": daño}))
                    msg_daño = resultado_daño["mensaje"]
                else:
                    msg_daño = "No hay objetivo al que aplicar el daño."

                narracion.append(_narrar( # Narramos el resultado del ataque exitoso
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. "
                    f"{'¡CRÍTICO! ' if critico else ''}ÉXITO. Daño: {daño}. {msg_daño}"
                ))
            else: # Si la acción no hace daño directo (empujar, cegar...) narramos el efecto especial
                efecto = evaluacion.get("efecto_exito", "")
                narracion.append(_narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. ÉXITO. Efecto: {efecto}"
                ))
        else: # Si no llega a la DC, el ataque falla
            efecto = evaluacion.get("efecto_fallo", "")
            narracion.append(_narrar(
                f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                f"{tirada}+{mod}={total} vs DC {dc}. FALLO. Efecto: {efecto}"
            ))

    estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id})) # Actualizamos el estado del combate tras el turno del jugador
    if estado["combate_terminado"]: # Si todos los enemigos han muerto, victoria
        narracion.append(_narrar("Todos los enemigos han caído. El jugador ha ganado el combate."))
        return _respuesta_turno(jugador, estado, "\n\n".join(narracion), "victoria")

    for e_resumen in estado.get("enemigos_vivos", [])[:2]: # Máximo 2 enemigos atacan por turno (el resto se posiciona)
        info = json.loads(get_info_entidad.invoke({"entidad_id": e_resumen["id"]})) # Cargamos la ficha completa del enemigo
        atributo_ataque = info.get("atributo_ataque", "fue") # Atributo del arma del enemigo (fallback a fue para entidades antiguas)
        if atributo_ataque not in ("fue", "des", "int"): # Validamos que sea un atributo válido, si no, fallback
            atributo_ataque = "fue"
        mod_enemigo = _modificador(info.get("atributos", {}).get(atributo_ataque, 2)) # Modificador del atributo de ataque
        tirada_enemigo = tirar_d20.invoke({}) # El enemigo tira su d20
        if ventaja_enemigos: # El jugador ha pifiado este turno: los enemigos tiran 2d20 y se quedan la mejor
            tirada_enemigo = max(tirada_enemigo, tirar_d20.invoke({}))
        critico_enemigo = (tirada_enemigo == 20) # Nat 20 = crítico (daño máximo)
        pifia_enemigo = (tirada_enemigo == 1) # Nat 1 = pifia (fallo automático con complicación)
        total_enemigo = tirada_enemigo + mod_enemigo # Total del ataque del enemigo

        if pifia_enemigo: # Nat 1: fallo automático con complicación narrativa
            narracion.append(_narrar(
                f"{info['nombre']} intenta atacar con {info.get('arma', 'sus garras')}. "
                f"NAT 1. ¡PIFIA! Narra una complicación dramática para el enemigo: tropieza, su arma se atasca, "
                f"se golpea a sí mismo o queda expuesto brevemente."
            ))
        elif critico_enemigo or total_enemigo >= jugador["ac"]: # Crítico o supera la AC
            dado = info.get("dado_daño", "1d4")
            if critico_enemigo: # Daño máximo del dado + modificador
                partes = dado.lower().split("d")
                cantidad = int(partes[0])
                caras = int(partes[1])
                daño_enemigo = (cantidad * caras) + mod_enemigo
            else:
                daño_enemigo = tirar_dado.invoke({"dado": dado}) + mod_enemigo
            daño_enemigo = max(1, daño_enemigo) # Daño mínimo 1
            jugador["vida_actual"] = max(0, jugador["vida_actual"] - daño_enemigo) # Restamos la vida, mínimo 0
            _guardar_jugador(jugador) # Guardamos la ficha actualizada del jugador
            narracion.append(_narrar( # Narramos el golpe del enemigo
                f"{info['nombre']} ataca al jugador con {info.get('arma', 'sus garras')}. "
                f"Tirada: {tirada_enemigo}+{mod_enemigo}={total_enemigo} vs AC {jugador['ac']} ({atributo_ataque.upper()}). "
                f"{'¡CRÍTICO! ' if critico_enemigo else ''}ACIERTA. Daño: {daño_enemigo}. Vida jugador: {jugador['vida_actual']}/{jugador['vida_max']}"
            ))
        else: # Si no llega a la AC, el ataque del enemigo falla
            narracion.append(_narrar(
                f"{info['nombre']} ataca al jugador con {info.get('arma', 'sus garras')}. "
                f"Tirada: {tirada_enemigo}+{mod_enemigo}={total_enemigo} vs AC {jugador['ac']} ({atributo_ataque.upper()}). FALLA."
            ))

    if jugador["vida_actual"] <= 0: # Si la vida del jugador llega a 0, derrota
        narracion.append(_narrar(f"{jugador['nombre']} cae derrotado. Narra su caída."))
        estado_final = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
        return _respuesta_turno(jugador, estado_final, "\n\n".join(narracion), "derrota")

    estado_final = json.loads(get_estado_combate.invoke({"beat_id": beat_id})) # Estado final del turno, el combate sigue
    return _respuesta_turno(jugador, estado_final, "\n\n".join(narracion), None) # Devolvemos el estado sin resultado porque el combate continúa


# ── CLI ──────────────────────────────────────────────────────────────────────

def combate(entidades_presentes: list) -> str: # Bucle de combate para la terminal, recibe las entidades presentes y devuelve "victoria" o "derrota"
    jugador = _cargar_jugador()

    if not entidades_presentes: # Si no hay entidades, victoria directa
        return "victoria"

    arma_turno = None # Arma elegida por el jugador, se mantiene entre turnos una vez elegida

    nombres = ", ".join( # Construimos el string con los nombres y stats de los enemigos para la narración inicial
        f"{e['nombre']} (AC:{e.get('ac', 10)}, HP:{e.get('vida_actual', '?')})"
        for e in entidades_presentes
    )
    arma_jugador = jugador.get("arma", {}).get("nombre", "sus puños") # Arma del jugador, si no tiene ninguna usa sus puños
    combate_msg(_narrar( # Narramos la intro del combate (solo ambientación, sin resolver acción)
        f"El jugador ({jugador['nombre']}, armado con {arma_jugador}) se enfrenta a: {nombres}. "
        f"Describe cómo irrumpe el combate de forma brusca e imprevista, presentando a los enemigos y la tensión del momento. "
        f"No resuelvas ningún ataque todavía."
    ))
    _mostrar_estado(jugador, entidades_presentes) # Mostramos el estado inicial del combate

    while True: # Bucle principal de combate, un turno por iteración
        accion = prompt_jugador() # Pedimos la acción al jugador

        if not accion: # Si no escribe nada, volvemos a pedir
            continue

        vivos = _get_vivos(entidades_presentes) # Consultamos qué entidades siguen vivas

        if not vivos: # Si no quedan vivas, salimos del bucle
            break

        armas_inv = get_armas(jugador) # Obtenemos las armas del inventario
        if armas_inv:
            verificacion = verificar_arma_en_accion(accion, armas_inv) # Comprobamos si menciona un arma
            if verificacion["estado"] == "no_en_inventario": # Si el arma no está en el inventario, lo narramos y pedimos otra acción
                nombres_armas = ", ".join(a["nombre"] for a in armas_inv)
                combate_msg(_narrar(
                    f"El jugador intenta usar '{verificacion['nombre']}' pero no lo tiene. "
                    f"Sus armas son: {nombres_armas}. Narra que no tiene esa arma."
                ))
                continue
            elif verificacion["estado"] == "encontrada": # Si el arma existe, la guardamos para este turno y los siguientes
                arma_turno = verificacion["arma"]
                jugador["arma"] = arma_turno
                _guardar_jugador(jugador) # Persistimos el cambio de arma inmediatamente

        arma_actual = arma_turno or jugador.get("arma", {}) # Usamos el arma del turno, o la que tenga equipada si no eligió ninguna
        consumibles = [i for i in jugador.get("inventario", []) if i.get("tipo") == "consumible"] # Items consumibles disponibles
        contexto = ( # Contexto completo para que el LLM evalúe la acción
            f"Jugador: {jugador['nombre']} ({jugador.get('clase', '?')}), "
            f"Arma: {arma_actual.get('nombre', 'sus puños')} (dado: {arma_actual.get('dado_daño', '1d6')}), "
            f"Atributos: {json.dumps(jugador.get('atributos', {}))}\n"
            f"Consumibles disponibles: {json.dumps(consumibles, ensure_ascii=False)}\n"
            f"Entidades presentes (vivas): {json.dumps(vivos, ensure_ascii=False)}"
        )

        evaluacion = _evaluar_accion(accion, contexto) # El LLM evalúa si la acción es viable y cómo resolverla

        if not evaluacion.get("viable", False): # Si no es viable, narramos el motivo y pedimos otra acción
            razon = evaluacion.get("razon", "Eso no es posible aquí.")
            combate_msg(_narrar(f"El jugador intenta: '{accion}'. No es viable: {razon}"))
            continue

        tipo = evaluacion.get("tipo", "accion") # "ataque" o "accion"

        if tipo == "ataque" and armas_inv and arma_turno is None: # Si es un ataque pero el jugador no ha elegido arma, se la pedimos
            nombres_armas = ", ".join(a["nombre"] for a in armas_inv)
            sistema_msg(f"¿Con qué arma atacas? Tienes: {nombres_armas}")
            eleccion = prompt_jugador()
            v2 = verificar_arma_en_accion(eleccion, armas_inv)
            if v2["estado"] == "encontrada": # Si elige un arma válida, la guardamos
                arma_turno = v2["arma"]
                jugador["arma"] = arma_turno
                _guardar_jugador(jugador) # Persistimos el cambio de arma inmediatamente
            else: # Si el arma no existe, lo informamos y pedimos otra acción
                combate_msg(f"No tienes esa arma. Armas disponibles: {nombres_armas}")
                continue

        if arma_turno: # Si hay arma elegida, sobreescribimos el dado de daño con el del inventario
            evaluacion["dado_daño"] = arma_turno.get("dado_daño", evaluacion.get("dado_daño", "1d6"))

        atributo = evaluacion.get("atributo", "fue") # Atributo para la tirada
        dc = evaluacion.get("dc", 12) # Dificultad a superar
        mod = _modificador(jugador.get("atributos", {}).get(atributo, 0)) # Modificador del jugador para ese atributo

        ventaja_enemigos = False # Se activa si el jugador saca pifia: los enemigos atacarán ese turno con ventaja

        # Si el jugador usa un item consumible, se resuelve sin tirada y consume el turno (los enemigos atacan igual más abajo)
        item_name = evaluacion.get("usa_item")
        if item_name:
            resultado_item = usar_item.invoke({"nombre_item": item_name})
            jugador = _cargar_jugador() # Recargamos para reflejar cambios en HP e inventario
            combate_msg(_narrar(
                f"El jugador usa '{item_name}'. Resultado: {resultado_item}. Narra el uso del item con color."
            ))
        else:
            tirada = tirar_d20.invoke({}) # Tiramos el d20
            critico = (tirada == 20 and tipo == "ataque") # Nat 20 en ataque = crítico
            pifia = (tirada == 1) # Nat 1 = pifia
            total = tirada + mod

            if pifia: # Pifia: fallo automático con complicación narrativa
                ventaja_enemigos = True # El jugador queda expuesto: los enemigos atacan con ventaja este turno
                combate_msg(_narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"NAT 1. ¡PIFIA! El ataque falla estrepitosamente y el jugador queda expuesto. "
                    f"Narra una complicación: el arma se atasca, el jugador tropieza, "
                    f"se golpea a sí mismo o queda expuesto."
                ))
            elif critico or total >= dc: # Acierto: crítico o supera la DC
                if evaluacion.get("termina_combate"): # La acción resuelve el combate sin victoria ni derrota
                    motivo = evaluacion.get("motivo_fin", "el combate termina por una resolución narrativa")
                    combate_msg(_narrar(
                        f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                        f"{tirada}+{mod}={total} vs DC {dc}. ÉXITO. "
                        f"El combate termina: {motivo}. Narra el desenlace con tensión."
                    ))
                    return "resolucion"

                dado_daño = evaluacion.get("dado_daño")
                objetivo_id = evaluacion.get("objetivo")

                if dado_daño: # Si hay daño que aplicar
                    if critico: # Crítico: daño máximo (todos los dados al máximo) + modificador
                        partes = dado_daño.lower().split("d")
                        cantidad = int(partes[0])
                        caras = int(partes[1])
                        daño = (cantidad * caras) + mod
                    else:
                        daño = tirar_dado.invoke({"dado": dado_daño}) + mod # Tirada normal + modificador
                    daño = max(1, daño) # Mínimo 1 de daño

                    if not objetivo_id and vivos: # Si no hay objetivo concreto, atacamos solo al primer vivo (no cleave AoE)
                        objetivo_id = vivos[0]["id"]
                    if objetivo_id: # Buscamos el tipo del objetivo para usar la tool correcta
                        entidad_objetivo = next(
                            (e for e in entidades_presentes if e["id"] == objetivo_id), None
                        )
                        tipo_entidad = entidad_objetivo.get("tipo_entidad", "enemigo") if entidad_objetivo else "enemigo"
                        if tipo_entidad == "npc": # Los NPCs y enemigos están en secciones distintas del JSON
                            resultado = json.loads(dañar_npc.invoke({"npc_id": objetivo_id, "daño": daño}))
                        else:
                            resultado = json.loads(dañar_enemigo.invoke({"enemigo_id": objetivo_id, "daño": daño}))
                        msg_daño = resultado["mensaje"]
                    else:
                        msg_daño = "No hay objetivo al que aplicar el daño."

                    combate_msg(_narrar( # Narramos el resultado del ataque
                        f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                        f"{tirada}+{mod}={total} vs DC {dc}. "
                        f"{'¡CRÍTICO! ' if critico else ''}ÉXITO. Daño: {daño}. {msg_daño}"
                    ))
                else: # Acción sin daño directo, narramos el efecto especial
                    efecto = evaluacion.get("efecto_exito", "")
                    combate_msg(_narrar(
                        f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                        f"{tirada}+{mod}={total} vs DC {dc}. ÉXITO. Efecto: {efecto}"
                    ))
            else: # Fallo: no llega a la DC
                efecto = evaluacion.get("efecto_fallo", "")
                combate_msg(_narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. FALLO. Efecto: {efecto}"
                ))

        vivos_actual = _get_vivos(entidades_presentes) # Comprobamos si quedan vivos tras el turno del jugador
        if not vivos_actual: # Si no quedan, el jugador ha ganado
            victoria_msg(_narrar(
                f"Todas las entidades han caído. El jugador triunfa en este enfrentamiento."
            ))
            return "victoria"

        for e in vivos_actual[:2]: # Máximo 2 enemigos atacan por turno (el resto se posiciona)
            info_raw = get_info_entidad.invoke({"entidad_id": e["id"]}) # Cargamos la ficha actualizada de la entidad
            try:
                info = json.loads(info_raw)
            except (json.JSONDecodeError, TypeError): # Si falla el parseo saltamos esta entidad
                continue

            atributo_ataque = info.get("atributo_ataque", "fue") # Atributo del arma de la entidad (fallback a fue)
            if atributo_ataque not in ("fue", "des", "int"): # Validamos que sea un atributo válido, si no, fallback
                atributo_ataque = "fue"
            mod_enemigo = _modificador(info.get("atributos", {}).get(atributo_ataque, 2)) # Modificador según el atributo de ataque
            tirada_enemigo = tirar_d20.invoke({}) # La entidad tira su d20
            if ventaja_enemigos: # El jugador ha pifiado este turno: los enemigos tiran 2d20 y se quedan la mejor
                tirada_enemigo = max(tirada_enemigo, tirar_d20.invoke({}))
            critico_enemigo = (tirada_enemigo == 20) # Nat 20 = crítico (daño máximo)
            pifia_enemigo = (tirada_enemigo == 1) # Nat 1 = pifia (fallo automático con complicación)
            total_enemigo = tirada_enemigo + mod_enemigo

            if pifia_enemigo: # Nat 1: fallo automático con complicación narrativa
                enemigo_msg(info['nombre'], _narrar(
                    f"{info['nombre']} intenta contraatacar con {info.get('arma', 'sus manos')}. "
                    f"NAT 1. ¡PIFIA! Narra una complicación dramática para el enemigo: tropieza, su arma se atasca, "
                    f"se golpea a sí mismo o queda expuesto brevemente."
                ))
            elif critico_enemigo or total_enemigo >= jugador["ac"]: # Crítico o supera la AC
                dado = info.get("dado_daño", "1d4")
                if critico_enemigo: # Daño máximo del dado + modificador
                    partes = dado.lower().split("d")
                    cantidad = int(partes[0])
                    caras = int(partes[1])
                    daño_enemigo = (cantidad * caras) + mod_enemigo
                else:
                    daño_enemigo = tirar_dado.invoke({"dado": dado}) + mod_enemigo
                daño_enemigo = max(1, daño_enemigo) # Mínimo 1 de daño
                jugador["vida_actual"] = max(0, jugador["vida_actual"] - daño_enemigo) # Restamos vida al jugador, mínimo 0
                _guardar_jugador(jugador) # Guardamos la ficha actualizada
                enemigo_msg(info['nombre'], _narrar( # Narramos el golpe de la entidad
                    f"{info['nombre']} contraataca al jugador con {info.get('arma', 'sus manos')}. "
                    f"Tirada: {tirada_enemigo}+{mod_enemigo}={total_enemigo} vs AC {jugador['ac']} ({atributo_ataque.upper()}). "
                    f"{'¡CRÍTICO! ' if critico_enemigo else ''}ACIERTA. Daño: {daño_enemigo}. "
                    f"Vida jugador: {jugador['vida_actual']}/{jugador['vida_max']}"
                ))
            else: # Si no llega a la AC, el ataque de la entidad falla
                enemigo_msg(info['nombre'], _narrar(
                    f"{info['nombre']} intenta contraatacar al jugador. "
                    f"Tirada: {tirada_enemigo}+{mod_enemigo}={total_enemigo} vs AC {jugador['ac']} ({atributo_ataque.upper()}). FALLA."
                ))

        if jugador["vida_actual"] <= 0: # Si la vida del jugador llega a 0, derrota
            derrota_msg(_narrar(
                f"{jugador['nombre']} cae con {jugador['vida_actual']} HP. Narra su caída."
            ))
            return "derrota"

        _mostrar_estado(jugador, entidades_presentes) # Mostramos el estado al inicio del siguiente turno
