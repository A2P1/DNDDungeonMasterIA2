from fastapi import APIRouter, HTTPException # APIRouter para agrupar endpoints, HTTPException para errores HTTP
from api.schemas import AccionJugadorRequest, RespuestaNarradorResponse, EstadoPartidaResponse # Schemas de validación
from agentes.director import campaña_existe, cargar_campaña # Para comprobar si hay campaña activa
from agentes.Narrador import narrador, narrador_inicio # Los dos modos del narrador: turno normal e inicio de partida
from services.routing import ( # Funciones de routing que deciden si la acción va al narrador o desencadena combate
    detectar_intento_ataque,
    get_entidades_presentes,
    hay_entidad_atacable,
    generar_enemigo_narrativo
)
from config import RESUMEN_PATH # Ruta al resumen narrativo acumulado de la partida

router = APIRouter( # Router de partida, todos sus endpoints empiezan por /partida
    prefix="/partida",
    tags=["Partida"]
)


def _get_beat_actual(campaña: dict) -> dict | None: # Devuelve el primer beat que no esté completado, o None si la campaña terminó
    for acto in campaña.get("actos", []):
        for beat in acto.get("beats", []):
            if not beat.get("completado", False): # El primer beat no completado es el beat activo
                return beat
    return None


def _campaña_completada(campaña: dict) -> bool: # Comprueba si todos los beats están completados
    return all(
        beat.get("completado", False)
        for acto in campaña.get("actos", [])
        for beat in acto.get("beats", [])
    )


@router.get("/estado", response_model=EstadoPartidaResponse)
def get_estado_partida(): # Devuelve el beat en curso, el resumen y si la campaña ha terminado
    if not campaña_existe():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña activa")
    campaña = cargar_campaña() # Cargamos la campaña del disco
    resumen = RESUMEN_PATH.read_text(encoding='utf-8').strip() if RESUMEN_PATH.exists() else "" # Leemos el resumen si existe
    return {
        "beat_actual": _get_beat_actual(campaña),
        "resumen": resumen,
        "campaña_completada": _campaña_completada(campaña)
    }


@router.get("/resumen")
def get_resumen(): # Devuelve solo el resumen narrativo acumulado hasta ahora
    if not RESUMEN_PATH.exists():
        return {"resumen": ""}
    return {"resumen": RESUMEN_PATH.read_text(encoding='utf-8').strip()}


@router.post("/accion", response_model=RespuestaNarradorResponse)
def enviar_accion(body: AccionJugadorRequest): # Recibe la acción del jugador, detecta si es un ataque y enruta en consecuencia
    if not campaña_existe():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña activa")

    resumen = RESUMEN_PATH.read_text(encoding='utf-8').strip() if RESUMEN_PATH.exists() else "" # Leemos el resumen para pasárselo al detector

    if resumen and detectar_intento_ataque(body.accion, resumen): # Solo comprobamos ataques si ya hay partida en marcha (hay resumen)
        entidades = get_entidades_presentes() # Primero buscamos entidades registradas en el beat activo

        if not entidades and hay_entidad_atacable(body.accion, resumen): # Si no hay entidades registradas pero el LLM detecta que hay alguien presente...
            entidades = generar_enemigo_narrativo(body.accion, resumen) # ...generamos una ficha temporal para ese enemigo narrativo

        if entidades: # Si hay entidades, iniciamos combate en vez de narrar la acción
            beat_id = entidades[0].get("beat_origen", "temp") # Usamos el beat_origen de la primera entidad (o "temp" si es narrativa)
            intro = narrador( # El narrador genera la introducción del combate para que la escena tenga continuidad
                f"[SISTEMA] El jugador intenta atacar: '{body.accion}'. "
                f"Narra el inicio del enfrentamiento de forma brusca, sin resolver ningún ataque todavía."
            )
            return { # Devolvemos tipo "combate_iniciado" para que el frontend sepa que tiene que cambiar de modo
                "texto": intro,
                "tipo": "combate_iniciado",
                "entidades": entidades, # Las entidades contra las que va a combatir
                "beat_id": beat_id # El beat_id que el frontend debe pasar a POST /combate/accion
            }

    # Si no hay intento de ataque (o no hay resumen todavía), el narrador procesa la acción normalmente
    texto = narrador(body.accion)
    return {"texto": texto, "tipo": "narracion"}


@router.post("/iniciar", response_model=RespuestaNarradorResponse)
def iniciar_partida(): # Inicia la partida desde el principio con la narración de apertura, solo se llama la primera vez
    if not campaña_existe():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña creada")
    campaña = cargar_campaña() # Cargamos la campaña para pasársela al narrador de inicio
    texto = narrador_inicio(campaña) # El narrador genera la narración de apertura con el contexto de la campaña
    return {"texto": texto, "tipo": "narracion"}
