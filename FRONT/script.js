import {get_campaña, iniciarPartida, accionPartida, borrarPartida, accionCombate } from './api.js' ; // Importamos las funciones de la API para usarlas en el frontend

let nombre = "";
let tema = "";

let modo = "setupPersonaje";
async function init() {
    try {
            const campaña = await get_campaña(); // Obtenemos la campaña al cargar la página
            if (campaña) {
                modo = "narrativa";
            }
    } catch (error) {
        Personaje();
    }
    
    document.getElementById("prompt-input").addEventListener('keydown', async function(event) {
        if (event.key === 'Enter') {
            let valor = document.getElementById("prompt-input").value;
            limpiarInput();
            if (modo === "narrativa") {
                let resultado = await accionPartida(valor);
                escribirTexto("\n\n" + resultado.texto); // Escribimos la narración que nos devuelve el backend en el textarea
            }
            if (modo === "setupPersonaje") {
                nombre = valor;
                modo = "setupCampaña";
                Campaña();
            }
            if (modo === "setupCampaña") {
                tema = valor;
                let inicio = await iniciarPartida(tema, nombre);
                escribirTexto("\n\n" + inicio.narracion_inicio); // Escribimos la narración de introducción a la campaña que nos devuelve el backend en el textarea
                modo = "narrativa";
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



