from agentes.Narrador import narrador, narrador_inicio
from agentes.director import generar_campaña, campaña_existe, cargar_campaña
from agentes.enriquecedor import enriquecer_entidades, entidades_existen
from agentes.combate import combate
from tools.campana import get_siguiente_beat, marcar_beat_completado
from dotenv import load_dotenv
from config import RESUMEN_PATH
import json


def iniciar_campaña():
    """Si no existe campaña, pregunta al jugador y genera una."""
    if campaña_existe():
        print("Campaña existente encontrada. Continuando...\n")
        campaña = cargar_campaña()
    else:
        print("=== CREACIÓN DE CAMPAÑA ===\n")
        tema = input("¿Qué tipo de aventura quieres? (ej: mazmorra oscura, bosque maldito, ciudad pirata): ")
        personaje = input("Describe tu personaje (ej: Thorin, enano guerrero): ")

        print("\nGenerando tu campaña... (esto puede tardar unos segundos)\n")
        campaña = generar_campaña(tema, personaje)
        print(f"¡Campaña '{campaña['titulo']}' creada!\n")
        print(f"Gancho: {campaña['gancho']}\n")

    # Enriquecer entidades si no existen
    if not entidades_existen():
        print("Generando fichas detalladas de enemigos y NPCs...\n")
        enriquecer_entidades(campaña)
        print("Fichas generadas.\n")

    return campaña


def _beat_es_combate():
    """Comprueba si el siguiente beat pendiente es de combate. Devuelve el beat o None."""
    raw = get_siguiente_beat.invoke({})
    if raw == "CAMPAÑA COMPLETADA":
        return None
    data = json.loads(raw)
    beat = data.get("beat", {})
    if beat.get("tipo") in ("combate", "jefe", "climax"):
        return beat
    return None


def main():
    load_dotenv()

    # Generar o cargar la campaña antes de empezar
    campaña = iniciar_campaña()

    while True:
        # Comprobar si el beat actual es de combate antes de pedir input
        beat_combate = _beat_es_combate()
        if beat_combate:
            resultado = combate(beat_combate["id"])
            marcar_beat_completado.invoke({"beat_id": beat_combate["id"]})
            continue

        with open(RESUMEN_PATH, 'r', encoding='utf-8') as f:
            resumen = f.read().strip()
        if resumen:
            user_input = input("Escribe tu mensaje (o 'salir' para terminar): \n")
            if user_input.lower() == "salir":
                break
            print(narrador(user_input))
        else:
            print(narrador_inicio())
main()

