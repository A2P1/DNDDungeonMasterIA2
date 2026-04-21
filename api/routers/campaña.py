from fastapi import APIRouter, HTTPException # APIRouter para agrupar endpoints, HTTPException para errores HTTP
from api.schemas import CrearCampañaRequest, CampañaResponse # Schemas de validación de entrada y salida
from agentes.director import generar_campaña as _generar_campaña, campaña_existe, cargar_campaña # Funciones del agente director
from agentes.enriquecedor import enriquecer_entidades # Para generar las fichas de enemigos tras crear la campaña
from config import CAMPAIGN_PATH, STATS_PATH, RESUMEN_PATH, ENTIDADES_PATH # Rutas de los archivos a limpiar al borrar

router = APIRouter( # Router de campaña, todos sus endpoints empiezan por /campaña
    prefix="/campaña",
    tags=["Campaña"] # Agrupa los endpoints en la documentación de Swagger
)


@router.get("/", response_model=CampañaResponse)
def get_campaña(): # Devuelve la campaña activa, o 404 si no hay ninguna
    if not campaña_existe():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña creada")
    return cargar_campaña() # Leemos el campaign.json y lo devolvemos


@router.post("/", response_model=CampañaResponse, status_code=201)
def crear_campaña(body: CrearCampañaRequest): # Genera una nueva campaña con el tema y el personaje que pasa el frontend
    campaña = _generar_campaña(body.tema, body.personaje) # El director genera la campaña
    enriquecer_entidades(campaña) # El enriquecedor genera las fichas de enemigos y NPCs automáticamente
    return campaña # Devolvemos la campaña recién creada


@router.delete("/", status_code=204)
def borrar_campaña(): # Borra la campaña y limpia todos los archivos de la partida para empezar de cero
    if not campaña_existe():
        raise HTTPException(status_code=404, detail="No hay ninguna campaña que borrar")
    for archivo in [CAMPAIGN_PATH, STATS_PATH, RESUMEN_PATH, ENTIDADES_PATH]: # Borramos todos los archivos de estado
        if archivo.exists(): # Solo intentamos borrar si el archivo existe
            archivo.unlink() # Lo eliminamos del disco
