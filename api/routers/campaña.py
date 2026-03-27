from fastapi import APIRouter, HTTPException
from api.schemas import CrearCampañaRequest, CampañaResponse

router = APIRouter(
    prefix="/campaña",  # Todas las rutas empezarán por /campaña
    tags=["Campaña"]    # Agrupa los endpoints por categorías
)


@router.get("/", response_model=CampañaResponse) 
def get_campaña(): # Devuelve la campaña actual, si no existe, devuelve 404
    pass


@router.post("/", response_model=CampañaResponse, status_code=201)
def crear_campaña(body: CrearCampañaRequest): # Crea una nueva campaña con el tema de la historia y la descripción del personaje
    pass


@router.delete("/", status_code=204)
def borrar_campaña(): # Elimina la campaña actual
    pass
