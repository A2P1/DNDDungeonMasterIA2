from fastapi import APIRouter, HTTPException
from api.schemas import CrearPersonajeRequest, PersonajeResponse

router = APIRouter(
    prefix="/personaje",
    tags=["Personaje"]
)


@router.get("/", response_model=PersonajeResponse)
def get_personaje(): # Devuelve la ficha del personaje, si no existe devuelve 404
    pass


@router.post("/", response_model=PersonajeResponse, status_code=201)
def crear_personaje(body: CrearPersonajeRequest): # Genera la ficha del personaje a partir de su descripción
    pass


@router.put("/", response_model=PersonajeResponse)
def actualizar_personaje(body: PersonajeResponse): # Actualiza los datos del personaje, útil para modificar stats desde el frontend
    pass
