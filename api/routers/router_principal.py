from fastapi import APIRouter, HTTPException # APIRouter para agrupar endpoints, HTTPException para errores HTTP
from api.schemas import IniciarResponse, IniciarRequest, AccionRequest, AccionResponse, AccionCombateRequest, EstadoCombateResponse # Schemas de validación de entrada y salida
from orquestador import crearimagenPaisaje, iniciar, borrar_campaña, comprobarCampaña, procesar_accion, obtenerInventario # Funciones del orquestador para iniciar y borrar la campaña
from agentes.combate import procesar_turno # Función del agente de combate para procesar un turno de combate
routerCampaña = APIRouter( # Router de campaña, todos sus endpoints empiezan por /campaña
    prefix="/campaña",
    tags=["Campaña"] # Agrupa los endpoints en la documentación de Swagger
)

routerAccion = APIRouter(
    prefix="/partida",
    tags=["Partida"] # Agrupa los endpoints en la documentación de Swagger
)

routerCombate = APIRouter(
    prefix="/combate",
    tags=["Combate"] # Agrupa los endpoints en la documentación de Swagger
)

# Comprueba si existe la campaña
@routerCampaña.get("/")
def get_campaña() -> bool:
    if not comprobarCampaña():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña creada")
    return True
@routerAccion.post("/imagen/lugar")
def mostrarImagen():
    if not comprobarCampaña():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña creada")
    ruta_imagen = crearimagenPaisaje()
    return {"ok": True}
@routerCampaña.get("/inventario")
def get_inventario():
    if not comprobarCampaña():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña creada")
    inventario = obtenerInventario()
    return {"inventario": inventario}

@routerCampaña.post("/iniciar", response_model=IniciarResponse, status_code=201)
def iniciarPartida(body: IniciarRequest): # Genera una nueva campaña con el tema y el personaje que pasa el frontend
    campaña = iniciar(body.tema, body.personaje) 
    return campaña

@routerAccion.post("/accion", response_model=AccionResponse) # Devuelve la acción
def accionPartida(body: AccionRequest):
    accion = procesar_accion(body.accion)
    return accion

@routerCampaña.delete("/", status_code=204)
def borrar_partida():
    if comprobarCampaña():
        borrar_campaña()
    else:
        raise HTTPException(status_code=404, detail="No hay ninguna campaña que borrar")

@routerCombate.post("/conflicto", response_model=EstadoCombateResponse) # Devuelve la acción
def accionCombate(body: AccionCombateRequest):
    estado_combate = procesar_turno(beat_id=body.beat_id, accion = body.accion)
    return estado_combate




