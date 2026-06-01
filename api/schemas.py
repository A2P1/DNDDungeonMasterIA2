from pydantic import BaseModel # Base para todos los schemas de validación
from typing import Optional # Para campos que pueden ser None




# SCHEMAS DE PERSONAJE

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



# SCHEMAS DE PARTIDA
class IniciarRequest(BaseModel): # Body del POST /partida/iniciar con el tema y personaje elegidos
    tema: str       # Tema de la campaña elegido por el jugador (ej: "mazmorra clásica")
    personaje: str  # Tipo de personaje elegido por el jugador (ej: "guerrero")

class IniciarResponse(BaseModel): # Respuesta del POST /partida/iniciar con toda la info para arrancar la partida
    campaña: dict           # Datos de la campaña recién creada
    stats: dict            # Stats iniciales del personaje (atributos, vida, arma equipada, etc)
    narracion_inicio: dict   # Narración de introducción a la campaña generada por el narrador

class AccionRequest(BaseModel): # Body del POST /partida/accion con lo que escribe el jugador
    accion: str  # Lo que escribe el jugador (ej: "Entro a la taberna")

class AccionResponse(BaseModel):
    tipo: str
    texto: str
    entidades: Optional[list] = None
    beat_id: Optional[str] = None  # Solo se devuelve beat_id si el tipo es "combate_iniciado"


# SCHEMAS DE COMBATE

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
    tirada: Optional[int] = None  # Resultado de la tirada de dado del jugador en su turno (solo en POST /accion)

# SCHEMAS DE INVENTARIO

class ObjetoInventarioRequest(BaseModel): # Body del POST /inventario/objeto para añadir un item
    nombre: str
    tipo: str                       # "arma" | "consumible" | "objeto"
    dado_daño: Optional[str] = None # Solo para armas (ej: "1d6")
    descripcion: Optional[str] = ""

