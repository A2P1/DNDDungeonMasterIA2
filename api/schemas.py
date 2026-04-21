from pydantic import BaseModel # Base para todos los schemas de validación
from typing import Optional # Para campos que pueden ser None


# SCHEMAS DE CAMPAÑA

class CrearCampañaRequest(BaseModel): # Body del POST /campaña para crear una nueva campaña
    tema: str       # Tipo de aventura (ej: "mazmorra oscura")
    personaje: str  # Descripción del personaje (ej: "Thorin, enano guerrero")

class CampañaResponse(BaseModel): # Respuesta con los datos principales de la campaña
    titulo: str
    gancho: str
    ambientacion: dict
    actos: list


# SCHEMAS DE PERSONAJE

class CrearPersonajeRequest(BaseModel): # Body del POST /personaje para generar una ficha nueva
    descripcion: str  # Descripción libre del personaje

class AtributosPersonaje(BaseModel): # Los 6 atributos del personaje en escala 0-5
    fue: int
    des: int
    con: int
    int_: int  # 'int' es palabra reservada en Python, por eso lleva guion bajo
    sab: int
    car: int

class ArmaPersonaje(BaseModel): # Datos básicos del arma equipada
    nombre: str
    dado_daño: str  # Ej: "1d8"

class PersonajeResponse(BaseModel): # Ficha completa del jugador que devuelve la API
    nombre: str
    clase: str
    raza: str
    vida_max: int
    vida_actual: int
    ac: int
    atributos: dict
    arma: dict
    inventario: Optional[list] = [] # Puede estar vacío si el personaje no tiene items


# SCHEMAS DE PARTIDA

class AccionJugadorRequest(BaseModel): # Body del POST /partida/accion con lo que escribe el jugador
    accion: str  # Lo que escribe el jugador (ej: "Entro a la taberna")

class RespuestaNarradorResponse(BaseModel): # Respuesta del narrador tras procesar la acción
    texto: str  # Narración generada
    tipo: str   # "narracion" | "combate_iniciado"
    entidades: Optional[list] = None  # Solo cuando tipo == "combate_iniciado": lista de entidades contra las que pelear
    beat_id: Optional[str] = None     # Solo cuando tipo == "combate_iniciado": id del beat (o "temp" para combate narrativo)

class EstadoPartidaResponse(BaseModel): # Estado general de la partida en un momento dado
    beat_actual: Optional[dict]  # Beat en curso (None si la campaña está completada)
    resumen: str                 # Resumen narrativo acumulado
    campaña_completada: bool     # True si todos los beats están superados


# SCHEMAS DE COMBATE

class IniciarCombateResponse(BaseModel): # Respuesta del POST /combate/iniciar con todo lo que el frontend necesita para arrancar el combate
    beat_id: str             # ID del beat de combate (ej: "b3"), para usarlo en POST /combate/accion
    descripcion: str         # Descripción del beat para dar contexto al frontend
    entidades: list          # Lista de entidades contra las que va a combatir el jugador
    narracion: str           # Narración de introducción del combate generada por el narrador

class AccionCombateRequest(BaseModel): # Body del POST /combate/accion con el turno del jugador
    beat_id: str  # ID del beat donde ocurre el combate (ej: "b2")
    accion: str   # Lo que hace el jugador en su turno (ej: "Ataco con mi espada larga")

class EstadoCombateResponse(BaseModel): # Estado del combate tras procesar un turno
    jugador_vida: int
    jugador_vida_max: int
    entidades_vivas: list        # Lista de entidades vivas con nombre y vida
    combate_terminado: bool
    resultado: Optional[str]     # "victoria" | "derrota" | "resolucion" | None si el combate sigue
    narracion: Optional[str] = None  # Texto narrado del turno (solo en POST /accion)
    loot: Optional[list] = None  # Items recogidos de los enemigos muertos (solo cuando resultado == "victoria" o "resolucion")


# SCHEMAS DE INVENTARIO

class ObjetoInventarioRequest(BaseModel): # Body del POST /inventario/objeto para añadir un item
    nombre: str
    tipo: str                       # "arma" | "consumible" | "objeto"
    dado_daño: Optional[str] = None # Solo para armas (ej: "1d6")
    descripcion: Optional[str] = ""

class InventarioResponse(BaseModel): # Respuesta con el inventario completo actualizado
    inventario: list  # Lista completa de objetos del jugador

class UsarItemRequest(BaseModel): # Body del POST /inventario/usar para consumir un item
    nombre: str  # Nombre del item a usar (ej: "Poción de cura")

class UsarItemResponse(BaseModel): # Respuesta tras usar un consumible
    mensaje: str             # Texto del efecto (ej: "Usas 'Poción de cura'. Recuperas 6 HP.")
    inventario: list         # Inventario actualizado (sin el item consumido)
    vida_actual: Optional[int] = None  # Nueva vida del jugador si el item curó HP (None si no curó)
