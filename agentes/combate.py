import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from typing import Callable, Literal, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from tools.entidades import dañar_enemigo, dañar_npc, get_info_entidad, get_estado_combate
from tools.dados import tirar_d20, tirar_dado
from tools.inventario import usar_item
from tools.campana import get_siguiente_beat # Para inyectar el beat actual como contexto narrativo del combate
from agentes.secretario import cargar_diario, guardar_diario, aplicar_delta, DeltaDiario # Para registrar el desenlace de cada combate en el diario
from config import STATS_PATH, COMBATE_PROMPT_PATH, ENTIDADES_PATH, COMBATE_MODEL, EVALUADOR_COMBATE_MODEL, DECISOR_NPC_MODEL # FIX-15: modelos por agente

load_dotenv()

with open(COMBATE_PROMPT_PATH, 'r', encoding='utf-8') as f:
    system_prompt_combate = f.read().strip()


class EvaluacionAccion(BaseModel):
    viable: bool
    razon: Optional[str] = None
    tipo: Optional[Literal["ataque", "accion"]] = None
    atributo: Optional[Literal["fue", "des", "con", "int", "sab", "car"]] = None
    dc: Optional[int] = Field(default=None, ge=8, le=20)
    dado_daño: Optional[str] = None
    arma_usada: Optional[str] = None # Nombre del arma del inventario que el LLM ha elegido para esta acción; el código verifica contra el inventario real antes de aplicar daño
    objetivo: Optional[str] = None
    efecto_exito: Optional[str] = None
    efecto_fallo: Optional[str] = None
    termina_combate: bool = False
    motivo_fin: Optional[str] = None
    usa_item: Optional[str] = None


class AccionNPC(BaseModel): # FIX-13: decisión por turno de un NPC. El LLM elige tipo (ataque/defensa/huida/habla/usa_item/espera) según contexto
    tipo: Literal["ataque", "defensa", "huida", "habla", "usa_item", "espera"]
    razon: Optional[str] = None # 1 frase de por qué el NPC toma esta decisión (su lógica interna)
    objetivo: Optional[str] = None # id del jugador (típicamente) o de otro enemigo si ataque
    atributo: Optional[Literal["fue", "des", "con", "int", "sab", "car"]] = None # Para tiradas (ataque o huida)
    dc: Optional[int] = Field(default=None, ge=8, le=20) # Para huida típicamente (default 10)
    dado_daño: Optional[str] = None # Solo si tipo == "ataque"
    arma_usada: Optional[str] = None # Solo si tipo == "ataque"
    dialogue: Optional[str] = None # Solo si tipo == "habla": lo que dice el NPC en primera persona (EXACTO)
    item_usado: Optional[str] = None # Solo si tipo == "usa_item"
    termina_combate: bool = False
    motivo_fin: Optional[str] = None


llm = ChatOpenAI(model=COMBATE_MODEL, temperature=0.9)
llm_evaluar = ChatOpenAI(model=EVALUADOR_COMBATE_MODEL, temperature=0.3).with_structured_output(EvaluacionAccion)
llm_decidir_npc = ChatOpenAI(model=DECISOR_NPC_MODEL, temperature=0.4).with_structured_output(AccionNPC) # FIX-13: temperatura media para algo de personalidad sin caos


def _get_tipo_entidad(entidad_id: str) -> str:
    if not ENTIDADES_PATH.exists():
        return "enemigo"
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
        entidades = json.load(f)
    for e in entidades.get("enemigos", []):
        if e["id"] == entidad_id:
            return "enemigo"
    for n in entidades.get("npcs", []):
        if n["id"] == entidad_id:
            return "npc"
    return "enemigo"




def _cargar_jugador() -> dict:
    if not STATS_PATH.exists():
        return {}
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _guardar_jugador(jugador: dict):
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(jugador, f, indent=2, ensure_ascii=False)


def _contexto_escena_msgs() -> list: # Beat + diario + entidades vivas del beat como SystemMessages: el LLM de combate no debe inventar lugar, NPCs ni armas
    msgs = []
    raw_beat = get_siguiente_beat.invoke({})
    beat_id = "" # Lo necesitamos para filtrar las entidades del beat actual
    if raw_beat == "CAMPAÑA COMPLETADA":
        msgs.append(SystemMessage(content="BEAT ACTUAL: campaña completada."))
    else:
        msgs.append(SystemMessage(content=f"BEAT ACTUAL (escena en la que ocurre el combate, respeta lugar y NPCs):\n{raw_beat}"))
        try:
            beat_id = json.loads(raw_beat).get("beat", {}).get("id", "")
        except (json.JSONDecodeError, AttributeError):
            pass
    diario = cargar_diario()
    msgs.append(SystemMessage(content=f"DIARIO (memoria de la partida, NO contradigas lo establecido):\n{diario.model_dump_json(indent=2, exclude_none=True)}"))
    if ENTIDADES_PATH.exists(): # Entidades vivas (enemigos del beat actual + NPCs activos): arma, descripción y atributos para que la narración no las invente
        with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
            entidades = json.load(f)
        relevantes = [e for e in entidades.get("enemigos", []) if e.get("beat_origen") == beat_id and e.get("estado") == "vivo"]
        relevantes += [n for n in entidades.get("npcs", []) if n.get("estado") == "vivo"]
        if relevantes:
            msgs.append(SystemMessage(content=f"ENTIDADES PRESENTES (respeta nombre, arma y descripción al narrar):\n{json.dumps(relevantes, indent=2, ensure_ascii=False)}"))
    return msgs


def _narrar(contexto: str) -> str:
    msgs = [
        SystemMessage(content=system_prompt_combate + "\n\nMODO: NARRAR"),
        *_contexto_escena_msgs(), # Inyectamos beat + diario para que el combate no invente ubicación ni mezcle el nombre del jugador con NPCs
        HumanMessage(content=contexto)
    ]
    return llm.invoke(msgs).content


def _evaluar_accion(accion: str, contexto_combate: str) -> dict:
    try:
        evaluacion = llm_evaluar.invoke([
            SystemMessage(content=system_prompt_combate + "\n\nMODO: EVALUAR ACCIÓN"),
            HumanMessage(content=f"Contexto del combate:\n{contexto_combate}\n\nAcción del jugador: {accion}")
        ])
        return evaluacion.model_dump(exclude_none=True)
    except Exception:
        return {"viable": False, "razon": "No se pudo interpretar la acción"}


def _decidir_accion_npc(npc_info: dict, jugador: dict, accion_jugador: str) -> dict: # FIX-13: el LLM decide la acción del NPC este turno según su ficha, HP, personalidad y la última acción del jugador
    hp_max = max(1, npc_info.get("vida_max", 1))
    hp_pct = round(100 * npc_info.get("vida_actual", 0) / hp_max)
    contexto = (
        f"NPC: {npc_info.get('nombre', '?')} (id: {npc_info.get('id', '?')})\n"
        f"Descripción: {npc_info.get('descripcion', '')}\n"
        f"HP: {npc_info.get('vida_actual', '?')}/{npc_info.get('vida_max', '?')} ({hp_pct}%)\n"
        f"Arma: {npc_info.get('arma') or 'sin arma específica'} (dado: {npc_info.get('dado_daño', '1d4')})\n"
        f"Atributos: {json.dumps(npc_info.get('atributos', {}))}\n"
        f"Jugador: {jugador.get('nombre', '?')} (HP: {jugador.get('vida_actual', '?')}/{jugador.get('vida_max', '?')})\n"
        f"Última acción del jugador: '{accion_jugador}'"
    )
    try:
        decision = llm_decidir_npc.invoke([
            SystemMessage(content=system_prompt_combate + "\n\nMODO: DECIDIR ACCIÓN NPC"),
            *_contexto_escena_msgs(),
            HumanMessage(content=contexto)
        ])
        return decision.model_dump(exclude_none=True)
    except Exception:
        return {"tipo": "ataque", "razon": "decisión por defecto"}


def _marcar_huido(entidad_id: str) -> None: # FIX-13: marca entidad como "huido" en entidades.json; get_estado_combate dejará de contarla
    if not ENTIDADES_PATH.exists():
        return
    with open(ENTIDADES_PATH, 'r', encoding='utf-8') as f:
        entidades = json.load(f)
    for grupo in ("enemigos", "npcs"):
        for e in entidades.get(grupo, []):
            if e.get("id") == entidad_id:
                e["estado"] = "huido"
    with open(ENTIDADES_PATH, 'w', encoding='utf-8') as f:
        json.dump(entidades, f, indent=2, ensure_ascii=False)


def _get_vivos(entidades: list) -> list:
    vivos = []
    for e in entidades:
        info_raw = get_info_entidad.invoke({"entidad_id": e["id"]})
        try:
            info = json.loads(info_raw)
            if info.get("estado") == "vivo":
                info["tipo_entidad"] = e.get("tipo_entidad", "enemigo")
                vivos.append(info)
        except (json.JSONDecodeError, TypeError):
            pass
    return vivos


def _respuesta_turno(jugador: dict, estado: dict, narracion: str, resultado, tirada: int, acciones_enemigos: Optional[list] = None) -> dict:
    if resultado in ("victoria", "derrota", "resolucion"): # Al cerrar combate, registramos el hecho en el diario para que el narrador se entere en el siguiente turno
        prefijo = {"victoria": "Combate ganado", "derrota": "Jugador derrotado en combate", "resolucion": "Combate resuelto sin matar a todos"}[resultado]
        primera_frase = narracion.split('.')[0][:200] # Primera frase de la narración para dar sabor sin inflar el diario
        diario = cargar_diario()
        guardar_diario(aplicar_delta(diario, DeltaDiario(hechos=[f"{prefijo}: {primera_frase}"])))
    return {
        "narracion": narracion,
        "jugador_vida": jugador["vida_actual"],
        "jugador_vida_max": jugador["vida_max"],
        "entidades_vivas": estado.get("enemigos_vivos", []),
        "combate_terminado": estado.get("combate_terminado", False),
        "resultado": resultado,
        "tirada": tirada,
        "acciones_enemigos": acciones_enemigos or [] # FIX-13: acciones individuales de cada NPC este turno (tipo, tirada, daño, dialogue, etc.)
    }


def procesar_turno(beat_id: str, accion: str) -> dict:
    jugador = _cargar_jugador()
    narracion = []
    tiro = None

    estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    enemigos_vivos = estado.get("enemigos_vivos", [])

    if not enemigos_vivos:
        return _respuesta_turno(jugador, estado, "No quedan enemigos.", "victoria", tiro)

    arma_actual = jugador.get("arma", {})
    armas_inv = [i for i in jugador.get("inventario", []) if i.get("tipo") == "arma"] # Inventario completo de armas: el LLM elegirá la apropiada según la acción del jugador
    consumibles = [i for i in jugador.get("inventario", []) if i.get("tipo") == "consumible"]
    contexto = (
        f"Jugador: {jugador['nombre']} ({jugador.get('clase', '?')})\n"
        f"Armas en inventario: {json.dumps(armas_inv, ensure_ascii=False)}\n"
        f"Arma equipada por defecto: {arma_actual.get('nombre', 'sus puños')} (dado: {arma_actual.get('dado_daño', '1d6')})\n"
        f"Atributos: {json.dumps(jugador.get('atributos', {}))}\n"
        f"Consumibles disponibles: {json.dumps(consumibles, ensure_ascii=False)}\n"
        f"Enemigos vivos: {json.dumps(enemigos_vivos, ensure_ascii=False)}"
    )
    evaluacion = _evaluar_accion(accion, contexto)

    if not evaluacion.get("viable", False):
        razon = evaluacion.get("razon", "Eso no es posible aquí.")
        texto = _narrar( # Prompt explícito: el LLM tendía a hacer eco de los datos en JSON; ahora le pedimos texto plano narrativo
            f"El jugador acaba de decir: '{accion}'. En combate, esa acción no es viable porque: {razon}. "
            f"INSTRUCCIÓN: narra en 1-2 frases breves, en tercera persona, que el jugador titubea o pierde el momento. "
            f"Devuelve SOLO la narración como texto plano. NO uses JSON, NO uses listas, NO uses comillas estructuradas."
        )
        if texto.strip().startswith("{"): # Red defensiva: si el LLM sigue devolviendo formato de datos, sustituimos por un mensaje neutro
            texto = f"{jugador.get('nombre', 'El guerrero')} titubea. Necesitas precisar mejor tu siguiente movimiento."
        return _respuesta_turno(jugador, estado, texto, None, tiro)

    tipo = evaluacion.get("tipo", "accion")
    atributo = evaluacion.get("atributo", "fue")
    dc = evaluacion.get("dc", 12)
    mod = jugador.get("atributos", {}).get(atributo, 0)

    # Para ataques, sobreescribimos dc con la AC real del objetivo (más fiable que confiar en el LLM)
    if evaluacion.get("tipo") == "ataque":
        objetivo_id_para_ac = evaluacion.get("objetivo") or (enemigos_vivos[0]["id"] if enemigos_vivos else None)
        if objetivo_id_para_ac:
            try:
                info_obj = json.loads(get_info_entidad.invoke({"entidad_id": objetivo_id_para_ac}))
                dc = info_obj.get("ac", dc) # si no hay ac válido, mantenemos el dc del LLM
            except (json.JSONDecodeError, TypeError):
                pass # si la consulta falla, mantenemos el dc del LLM como red de seguridad

    ventaja_enemigos = False

    item_name = evaluacion.get("usa_item")
    if item_name:
        resultado_item = usar_item.invoke({"nombre_item": item_name})
        jugador = _cargar_jugador()
        narracion.append(_narrar(
            f"El jugador usa '{item_name}'. Resultado: {resultado_item}. Narra el uso del item con color."
        ))
    else:
        tirada = tirar_d20.invoke({})
        if jugador.get("ventaja_proximo_turno"): # Si en el turno anterior un enemigo pifió, el jugador ataca con ventaja: tira 2d20 y se queda con la mejor
            tirada = max(tirada, tirar_d20.invoke({}))
            jugador["ventaja_proximo_turno"] = False # Consumimos el flag para que solo aplique a este ataque
            _guardar_jugador(jugador)
        critico = (tirada == 20 and tipo == "ataque")
        pifia = (tirada == 1)
        total = tirada + mod
        tiro = tirada
        if pifia:
            ventaja_enemigos = True
            narracion.append(_narrar(
                f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                f"NAT 1. ¡PIFIA! El ataque falla estrepitosamente y el jugador queda expuesto. "
                f"Narra una complicación dramática y memorable, siendo creativo: puede involucrar al entorno, a los enemigos cercanos, "
                f"a objetos del lugar o cualquier cosa que tenga sentido en la escena. Evita repetir el mismo tipo de complicación cada vez."
            ))
        elif critico or total >= dc:
            if evaluacion.get("termina_combate"):
                motivo = evaluacion.get("motivo_fin", "el combate termina por una resolución narrativa")
                texto = _narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. ÉXITO. "
                    f"El combate termina: {motivo}. Narra el desenlace con tensión."
                )
                return _respuesta_turno(jugador, estado, texto, "resolucion", tiro)

            dado_daño = evaluacion.get("dado_daño")
            arma_usada_nombre = evaluacion.get("arma_usada") # Si el LLM identificó un arma del inventario, sobreescribimos dado_daño con el valor real del inventario (single source of truth)
            if arma_usada_nombre:
                arma_inv = next((a for a in jugador.get("inventario", []) if a.get("tipo") == "arma" and a["nombre"].lower() == arma_usada_nombre.lower()), None)
                if arma_inv and arma_inv.get("dado_daño"):
                    dado_daño = arma_inv["dado_daño"]
            if dado_daño:
                if critico:
                    partes = dado_daño.lower().split("d")
                    cantidad = int(partes[0])
                    caras = int(partes[1])
                    daño = (cantidad * caras) + mod
                else:
                    daño = tirar_dado.invoke({"dado": dado_daño}) + mod
                daño = max(1, daño)

                objetivo_id = evaluacion.get("objetivo")
                if not objetivo_id and enemigos_vivos:
                    objetivo_id = enemigos_vivos[0]["id"]
                if objetivo_id:
                    tipo_entidad = _get_tipo_entidad(objetivo_id)
                    if tipo_entidad == "npc":
                        resultado = json.loads(dañar_npc.invoke({"npc_id": objetivo_id, "daño": daño}))
                    else:
                        resultado = json.loads(dañar_enemigo.invoke({"enemigo_id": objetivo_id, "daño": daño}))
                    msg_daño = resultado["mensaje"]
                else:
                    msg_daño = "No hay objetivo al que aplicar el daño."

                narracion.append(_narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. "
                    f"{'¡CRÍTICO! ' if critico else ''}ÉXITO. Daño: {daño}. {msg_daño}"
                ))
            else:
                efecto = evaluacion.get("efecto_exito", "")
                narracion.append(_narrar(
                    f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                    f"{tirada}+{mod}={total} vs DC {dc}. ÉXITO. Efecto: {efecto}"
                ))
        else:
            efecto = evaluacion.get("efecto_fallo", "")
            narracion.append(_narrar(
                f"Jugador: '{accion}'. Check de {atributo.upper()}: "
                f"{tirada}+{mod}={total} vs DC {dc}. FALLO. Efecto: {efecto}"
            ))

    estado = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    if estado["combate_terminado"]:
        narracion.append(_narrar("Todos los enemigos han caído. El jugador ha ganado el combate."))
        return _respuesta_turno(jugador, estado, "\n\n".join(narracion), "victoria", tiro)

    acciones_enemigos = [] # FIX-13: cada NPC decide su acción este turno; registramos qué hizo cada uno para que el frontend pueda mostrarlo
    for e_resumen in estado.get("enemigos_vivos", [])[:2]:
        info = json.loads(get_info_entidad.invoke({"entidad_id": e_resumen["id"]}))
        decision = _decidir_accion_npc(info, jugador, accion) # El LLM decide qué hace este NPC este turno (ataque/defensa/huida/habla/usa_item/espera)
        tipo_npc = decision.get("tipo", "ataque")
        accion_data = {"nombre": info["nombre"], "tipo": tipo_npc, "razon": decision.get("razon")}

        if tipo_npc == "ataque":
            atributo_ataque = decision.get("atributo") or info.get("atributo_ataque", "fue")
            if atributo_ataque not in ("fue", "des", "int"):
                atributo_ataque = "fue"
            mod_enemigo = info.get("atributos", {}).get(atributo_ataque, 0)
            tirada_enemigo = tirar_d20.invoke({})
            if ventaja_enemigos:
                tirada_enemigo = max(tirada_enemigo, tirar_d20.invoke({}))
            critico_enemigo = (tirada_enemigo == 20)
            pifia_enemigo = (tirada_enemigo == 1)
            total_enemigo = tirada_enemigo + mod_enemigo
            arma_npc = decision.get("arma_usada") or info.get("arma") or "la forma de ataque apropiada a su descripción"
            accion_data.update({"tirada": tirada_enemigo, "total": total_enemigo, "arma": arma_npc})

            if pifia_enemigo:
                jugador["ventaja_proximo_turno"] = True # Simetría con el jugador: la pifia enemiga deja al jugador en posición ventajosa para su siguiente ataque
                _guardar_jugador(jugador)
                accion_data["resultado"] = "pifia"
                narracion.append(_narrar(
                    f"{info['nombre']} intenta atacar con {arma_npc}. "
                    f"NAT 1. ¡PIFIA! Narra una complicación dramática y memorable, siendo creativo: puede involucrar al entorno, "
                    f"a sus aliados, a objetos del lugar o a su propio cuerpo. Evita repetir el mismo tipo de complicación cada vez. "
                    f"El jugador queda en posición ventajosa para responder."
                ))
            elif critico_enemigo or total_enemigo >= jugador["ac"]:
                dado = decision.get("dado_daño") or info.get("dado_daño", "1d4")
                if critico_enemigo:
                    partes = dado.lower().split("d")
                    cantidad = int(partes[0])
                    caras = int(partes[1])
                    daño_enemigo = (cantidad * caras) + mod_enemigo
                else:
                    daño_enemigo = tirar_dado.invoke({"dado": dado}) + mod_enemigo
                daño_enemigo = max(1, daño_enemigo)
                jugador["vida_actual"] = max(0, jugador["vida_actual"] - daño_enemigo)
                _guardar_jugador(jugador)
                accion_data["resultado"] = "critico" if critico_enemigo else "acierta"
                accion_data["daño"] = daño_enemigo
                narracion.append(_narrar(
                    f"{info['nombre']} ataca al jugador con {arma_npc}. "
                    f"Tirada: {tirada_enemigo}+{mod_enemigo}={total_enemigo} vs AC {jugador['ac']} ({atributo_ataque.upper()}). "
                    f"{'¡CRÍTICO! ' if critico_enemigo else ''}ACIERTA. Daño: {daño_enemigo}. Vida jugador: {jugador['vida_actual']}/{jugador['vida_max']}"
                ))
            else:
                accion_data["resultado"] = "falla"
                narracion.append(_narrar(
                    f"{info['nombre']} ataca al jugador con {arma_npc}. "
                    f"Tirada: {tirada_enemigo}+{mod_enemigo}={total_enemigo} vs AC {jugador['ac']} ({atributo_ataque.upper()}). FALLA."
                ))
        elif tipo_npc == "huida":
            atributo_huida = decision.get("atributo") or "des"
            if atributo_huida not in ("fue", "des", "con", "int", "sab", "car"):
                atributo_huida = "des"
            mod_huida = info.get("atributos", {}).get(atributo_huida, 0)
            tirada_huida = tirar_d20.invoke({})
            total_huida = tirada_huida + mod_huida
            dc_huida = decision.get("dc") or 10
            accion_data.update({"tirada": tirada_huida, "total": total_huida})
            if total_huida >= dc_huida:
                _marcar_huido(info["id"]) # Sale del combate (get_estado_combate ya no lo cuenta como vivo)
                accion_data["resultado"] = "huye"
                narracion.append(_narrar(
                    f"{info['nombre']} intenta huir del combate. Tirada {atributo_huida.upper()}: {tirada_huida}+{mod_huida}={total_huida} vs DC {dc_huida}. ÉXITO. "
                    f"Motivo: {decision.get('razon', 'instinto de supervivencia')}. "
                    f"Narra cómo escapa de la escena dejando atrás al jugador."
                ))
            else:
                accion_data["resultado"] = "huida_fallida"
                narracion.append(_narrar(
                    f"{info['nombre']} intenta huir pero falla. Tirada: {tirada_huida}+{mod_huida}={total_huida} vs DC {dc_huida}. "
                    f"Narra el intento fallido: queda en combate, jadeando o atrapado."
                ))
        elif tipo_npc == "habla":
            dialogue = decision.get("dialogue", "")
            accion_data["dialogue"] = dialogue
            accion_data["resultado"] = "habla"
            narracion.append(_narrar(
                f"{info['nombre']} habla en mitad del combate. Dice EXACTAMENTE: \"{dialogue}\". "
                f"Motivo interno del NPC: {decision.get('razon', '')}. "
                f"Narra la pausa de la acción, el tono de su voz y el efecto en la escena. NO inventes lo que dice; usa el dialogue EXACTO entre comillas."
            ))
        elif tipo_npc == "usa_item":
            item_nombre = decision.get("item_usado", "un objeto")
            accion_data["item"] = item_nombre
            accion_data["resultado"] = "usa_item"
            narracion.append(_narrar(
                f"{info['nombre']} usa '{item_nombre}' en mitad del combate. Motivo: {decision.get('razon', '')}. "
                f"Narra el uso del item con color (gesto, efecto visible)."
            ))
        elif tipo_npc == "defensa":
            accion_data["resultado"] = "defensa"
            narracion.append(_narrar(
                f"{info['nombre']} adopta postura defensiva. Motivo: {decision.get('razon', '')}. "
                f"Narra cómo se cubre, se prepara o retrocede sin huir."
            ))
        else: # espera (también default si llega un tipo desconocido)
            accion_data["resultado"] = "espera"
            narracion.append(_narrar(
                f"{info['nombre']} no ataca; espera, estudiando al jugador. Motivo: {decision.get('razon', '')}. "
                f"Narra la tensión del momento, su postura y lo que parece estar planeando."
            ))

        acciones_enemigos.append(accion_data)

    if jugador["vida_actual"] <= 0:
        narracion.append(_narrar(f"{jugador['nombre']} cae derrotado. Narra su caída."))
        estado_final = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
        return _respuesta_turno(jugador, estado_final, "\n\n".join(narracion), "derrota", tiro, acciones_enemigos)

    estado_final = json.loads(get_estado_combate.invoke({"beat_id": beat_id}))
    if estado_final.get("combate_terminado"): # FIX-13: si todos los NPCs huyeron este turno, combate resuelto sin matar a nadie
        return _respuesta_turno(jugador, estado_final, "\n\n".join(narracion), "resolucion", tiro, acciones_enemigos)
    return _respuesta_turno(jugador, estado_final, "\n\n".join(narracion), None, tiro, acciones_enemigos)


def combate(entidades_presentes: list) -> str:
    jugador = _cargar_jugador()

    if not entidades_presentes:
        return "victoria"

    nombres = ", ".join( # Incluimos arma y descripción: sin esto el LLM inventa armas (ej. "garras" para una flautista)
        f"{e['nombre']} [arma: {e.get('arma') or '?'}, descripción: {e.get('descripcion', '')}] (AC:{e.get('ac', 10)}, HP:{e.get('vida_actual', '?')})"
        for e in entidades_presentes
    )
    arma_jugador = jugador.get("arma", {}).get("nombre", "sus puños")
    return _narrar(
        f"El jugador ({jugador['nombre']}, armado con {arma_jugador}) se enfrenta a: {nombres}. "
        f"Describe cómo irrumpe el combate de forma brusca e imprevista, respetando arma y descripción de cada entidad. "
        f"No resuelvas ningún ataque todavía."
    )