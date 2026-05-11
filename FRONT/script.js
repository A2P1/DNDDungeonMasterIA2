import {get_campaña, iniciarPartida, accionPartida, borrarPartida, accionCombate } from './api.js' ; // Importamos las funciones de la API para usarlas en el frontend

let nombre = "";
let tema = "";
let beat = "";
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
                escribirTexto("\n\n> " + valor); // Escribimos el comando que el usuario ha introducido en el textarea
                escribirTexto("\n------------------------------------------------------------------------------------------\n")
                let resultado = await accionPartida(valor);
                console.log("resultado:", resultado);
                if (resultado.tipo === "combate_iniciado") {
                    beat = resultado.beat_id;
                    modo = "combate";
                    escribirTexto("Entidades presentes: " + resultado.entidades.map(e => e.nombre).join(", ")); // Escribimos las entidades presentes en el combate
                    escribirTexto("\n\n" + resultado.texto); // Escribimos la narración del combate que nos devuelve el backend en el textarea
                } else{
                    escribirTexto("\n\n" + resultado.texto); // Escribimos la narración que nos devuelve el backend en el textarea
                }
            } else if (modo === "setupPersonaje") {
                nombre = valor;
                escribirTexto("\n\n¡Bienvenido, " + nombre + "!"); // Escribimos un mensaje de bienvenida con el nombre del personaje que el usuario ha introducido
                modo = "setupCampaña";
                Campaña();
            } else if (modo === "setupCampaña") {
                tema = valor;
                escribirTexto("\n\nHas elegido una campaña de " + tema + ". ¡Que comience la aventura!"); // Escribimos un mensaje con el tema de la campaña que el usuario ha introducido
                escribirTexto("\n\nIniciando partida..."); // Escribimos un mensaje de que se está iniciando la partida
                let inicio = await iniciarPartida(tema, nombre);
                limpiarNarracion();
                escribirTexto("\n\n" + inicio.narracion_inicio.texto); // Escribimos la narración de introducción a la campaña que nos devuelve el backend en el textarea
                modo = "narrativa";
            } else if (modo === "combate") {
                
                let conflicto = await accionCombate(beat, valor);
                escribirTexto("\n\n" + conflicto.narracion); // Escribimos la narración del combate que nos devuelve el backend en el textarea
                escribirTexto("\n\n --------ESTADO COMBATE-------- \n");
                escribirTexto("Vida del jugador: " + conflicto.jugador_vida + " / " + conflicto.jugador_vida_max + "\n");
                escribirTexto("Enemigos vivos: " + conflicto.entidades_vivas.map(e => e.nombre + ": " + e.vida).join(", ") + "\n");
                if (conflicto.tirada != null)
                    escribirTexto("Tirada de dados: " + conflicto.tirada + "/20\n");
                escribirTexto("\n ---------------- \n");
                if (conflicto.combate_terminado === true) {
                    modo = "narrativa";
                }
            }
            

        }
    });
            
    document.getElementById("borrar-button").addEventListener('click', async function() {
        await borrar();
        location.reload(); // Recargamos la página para empezar una nueva partida
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
function limpiarNarracion(){
    document.getElementById("narration").value = "";
}

async function borrar() {
    await borrarPartida();
}



