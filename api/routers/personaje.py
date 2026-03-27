from fastapi import APIRouter, HTTPException
from api.schemas import CrearPersonajeRequest, PersonajeResponse

router = APIRouter(
    prefix="/personaje",
    tags=["Personaje"]
)


@router.get("/", response_model=PersonajeResponse)
def get_personaje(): # Devuelve los datos del personaje
    """Devuelve la ficha completa del personaje desde stats.json.
    Si no existe ficha creada, devuelve 404."""
    pass


@router.post("/", response_model=PersonajeResponse, status_code=201)
def crear_personaje(body: CrearPersonajeRequest): # Crea un personaje nuevo
    pass


@router.put("/", response_model=PersonajeResponse)
def actualizar_personaje(body: PersonajeResponse): # Actualiza los datos del personaje
    pass
