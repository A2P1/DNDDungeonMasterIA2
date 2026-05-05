import {obtenerPersonaje, crearPersonaje, obtenerCampaña, crearCampaña, borrarCampaña, iniciarCombate, obtenerEstadoCombate, accionCombate, obtenerInventario, usarItemInventario, añadirObjetoInventario, eliminarObjetoInventario, obtenerEstadoPartida, obtenerResumenPartida, accionPartida, iniciarPartida} from './api.js' ; // Importamos las funciones de la API para usarlas en el frontend

let nombre = "";
let tema = "";

let modo = "setupPersonaje";
async function init() {
    try {
            const personaje = await obtenerPersonaje(); // Obtenemos el personaje al cargar la página
            const campaña = await obtenerCampaña(); // Obtenemos la campaña al cargar la página
            //if (personaje && campaña)
                //llamar narracion
    } catch (error) {
        Personaje();
    }
    
    document.getElementById("prompt-input").addEventListener('keydown', function(event) {
        if (event.key === 'Enter') {
            let valor = document.getElementById("prompt-input").value;
            limpiarInput();
            if (modo === "setupPersonaje") {
                nombre = valor;
                crearPersonaje(nombre);
                modo = "setupCampaña";
                Campaña();
            }
            if (modo === "setupCampaña") {
                tema = valor;
                crearCampaña(tema, nombre);
            } 

        }
    });
            
            



}
function escribirTexto(texto) {
        document.getElementById("narration").value += texto; // Obtenemos el valor del textarea con el id pasado como argumento
}

document.addEventListener("DOMContentLoaded", init); // Esperamos a que el contenido de la página se haya cargado para ejecutar la función init{

function Personaje() {
    escribirTexto("\n CREACIÓN DE PERSONAJE \n");
    escribirTexto("Describe tu personaje (ej: Thorin, enano guerrero)\n");
}

function Campaña() {
    escribirTexto("\n\n CREACIÓN DE CAMPAÑA \n");
    escribirTexto("¿Qué tipo de aventura quieres? (ej: mazmorra oscura, bosque maldito, ciudad pirata)\n");
}
function limpiarInput() {
    document.getElementById("prompt-input").value = "";
}



