from fastapi import APIRouter, HTTPException
from api.schemas import CrearCampañaRequest, CampañaResponse
from agentes.director import generar_campaña as _generar_campaña, campaña_existe, cargar_campaña
from agentes.enriquecedor import enriquecer_entidades
from config import CAMPAIGN_PATH, STATS_PATH, RESUMEN_PATH, ENTIDADES_PATH

router = APIRouter(
    prefix="/campaña",
    tags=["Campaña"]
)


@router.get("/", response_model=CampañaResponse)
def get_campaña(): # Devuelve la campaña actual, si no existe devuelve 404
    if not campaña_existe():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña creada")
    return cargar_campaña()


@router.post("/", response_model=CampañaResponse, status_code=201)
def crear_campaña(body: CrearCampañaRequest): # Crea una nueva campaña con el tema y el personaje
    campaña = _generar_campaña(body.tema, body.personaje)
    enriquecer_entidades(campaña)
    return campaña


@router.delete("/", status_code=204)
def borrar_campaña(): # Borra la campaña actual y limpia todos los archivos de la partida
    if not campaña_existe():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña que borrar")
    for archivo in [CAMPAIGN_PATH, STATS_PATH, RESUMEN_PATH, ENTIDADES_PATH]:
        if archivo.exists():
            archivo.unlink()

