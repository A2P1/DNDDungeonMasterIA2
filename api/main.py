from fastapi import FastAPI # El framework que usamos para montar la API REST
from api.routers import campaña, personaje, partida, combate, inventario # Los routers de cada sección
from fastapi.middleware.cors import CORSMiddleware # Permite conectar con el front
app = FastAPI( # Creamos la aplicación FastAPI con su metadata
    title="DnD Dungeon Master IA",
    description="API REST para conectar el backend de la IA con el frontend del juego",
    version="1.0.0"
)
app.add_middleware( # Configuramos CORS para permitir peticiones desde el frontend
    CORSMiddleware,
    allow_origins=["*"], # Permite todas las fuentes
    allow_methods=["*"], # Permite todos los métodos HTTP
    allow_headers=["*"], # Permite todas las cabeceras
)


# Registramos cada router con su grupo de endpoints
app.include_router(campaña.router)    # /campaña  → crear, cargar y borrar la campaña
app.include_router(personaje.router)  # /personaje → crear y consultar la ficha del jugador
app.include_router(partida.router)    # /partida  → enviar acciones al narrador y consultar el estado
app.include_router(combate.router)    # /combate  → procesar turnos de combate y consultar el estado
app.include_router(inventario.router) # /inventario → gestionar el inventario del jugador


@app.get("/")
def root(): # Endpoint de salud para comprobar que la API está activa
    return {"estado": "ok", "mensaje": "DnD Dungeon Master IA en línea"}
