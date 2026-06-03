import {get_campaña, iniciarPartida, accionPartida, borrarPartida, accionCombate, get_inventario, imagenLugar } from './api.js' ; // Importamos las funciones de la API para usarlas en el frontend

let nombre = "";
let tema = "";
let beat = "";
let modo = "setupPersonaje";

async function init() {
    try {
            const campaña = await get_campaña(); // Obtenemos la campaña al cargar la página
            if (campaña) {
                document.getElementById("imagenlugar").style.display = "flex";
                document.getElementById("imagen1").style.display = "block";
                document.getElementById("imagen2").style.display = "block";
                
                document.getElementById("imagen1").src = "http://localhost:8000/static/personaje.png?t=" + Date.now();
                //document.getElementById("imagen2").src = "http://localhost:8000/static/mundo.png?t=" + Date.now();
                document.body.style.backgroundImage = "url(http://localhost:8000/static/mundo.png?t=" + Date.now() + ")";
                modo = "narrativa";
                actualizarInventario();
            }
    } catch (error) {
        Personaje();
    }
    document.getElementById("prompt-input").addEventListener('keydown', async function(event) {
        if (event.key === 'Enter') {
            let valor = document.getElementById("prompt-input").value;
            limpiarInput();
            if (modo === "narrativa") {
                escribirTextoUsuario("> " + valor); // Escribimos el comando que el usuario ha introducido en el textarea
                let resultado = await accionPartida(valor);
                console.log("resultado:", resultado);
                if (resultado.tipo === "combate_iniciado") {
                    beat = resultado.beat_id;
                    modo = "combate";
                    escribirTextoIA("Entidades presentes: " + resultado.entidades.map(e => e.nombre).join(", ")); // Escribimos las entidades presentes en el combate
                    escribirTextoIA("\n" + resultado.texto); // Escribimos la narración del combate que nos devuelve el backend en el textarea
                } else{
                    escribirTextoIA("\n" + resultado.texto); // Escribimos la narración que nos devuelve el backend en el textarea
                }
                actualizarInventario();
            } else if (modo === "setupPersonaje") {
                nombre = valor;
                escribirTextoIA("\n¡Bienvenido, " + nombre + "!"); // Escribimos un mensaje de bienvenida con el nombre del personaje que el usuario ha introducido
                modo = "setupCampaña";
                Campaña();
            } else if (modo === "setupCampaña") {
                tema = valor;
                escribirTextoIA("\n\nHas elegido una campaña de " + tema + ". ¡Que comience la aventura!");
                escribirTextoIA("\n\nIniciando partida ...");
                let inicio = await iniciarPartida(tema, nombre);
                document.getElementById("imagenlugar").style.display = "flex";
                document.getElementById("imagen1").style.display = "block";
                document.getElementById("imagen1").src = "http://localhost:8000/static/personaje.png?t=" + Date.now();
                document.body.style.backgroundImage = "url(http://localhost:8000/static/mundo.png?t=" + Date.now() + ")";
                actualizarInventario();
                limpiarNarracion();
                escribirTextoIA("\n\n" + inicio.narracion_inicio.texto);
    modo = "narrativa";
            } else if (modo === "combate") {
                escribirTextoUsuarioCombate("\n> " + valor); // Escribimos el comando que el usuario ha introducido en el textarea
                let conflicto = await accionCombate(beat, valor);
                escribirTextoIA("\n" + conflicto.narracion); // Escribimos la narración del combate que nos devuelve el backend en el textarea
                escribirTextoIA("\n --------ESTADO COMBATE-------- \n");
                escribirTextoIA("Vida del jugador: " + conflicto.jugador_vida + " / " + conflicto.jugador_vida_max + "\n");
                escribirTextoIA("Enemigos vivos: " + conflicto.entidades_vivas.map(e => e.nombre + ": " + e.vida).join(", ") + "\n");
                if (conflicto.tirada != null)
                    escribirTextoIA("Tirada de dados: " + conflicto.tirada + "/20\n"); // Arreglar esto
                escribirTextoIA("\n ---------------- \n");
                if (conflicto.combate_terminado === true) {
                    modo = "narrativa";
                }
                if (conflicto.jugador_vida <= 0) {
                    escribirTextoIA("\n\n============================== GAME OVER ==============================\n");
                    await borrar();
                }
                actualizarInventario();
            }
            

        }
    });
            
    document.getElementById("borrar-button").addEventListener('click', async function() {
        await borrar();
        location.reload(); // Recargamos la página para empezar una nueva partida
        limpiarNarracion();
    });
    document.getElementById("imagen-lugar-button").addEventListener('click', async function() {
        escribirTextoIA("\nGenerando la imagen. Por favor espere...\n");
        await imagenLugar();
        document.getElementById("imagen2").src = "http://localhost:8000/static/puntoVista.png?t=" + Date.now(); // Actualizamos la imagen del lugar con la nueva imagen generada por el backend
        
    });


}
function escribirTextoUsuario(texto) {
        const textoFormateado = texto.replace(/\n/g, '<br>');
        document.getElementById("narration").innerHTML += '<p style="color: blue; font-weight: bold;">' + textoFormateado + '</p>'; // Obtenemos el valor del textarea con el id pasado como argumento
}
function escribirTextoUsuarioCombate(texto) {
        const textoFormateado = texto.replace(/\n/g, '<br>');
        document.getElementById("narration").innerHTML += '<p style="color: red; font-weight: bold;">' + textoFormateado + '</p>'; // Obtenemos el valor del textarea con el id pasado como argumento
}
function escribirTextoIA(texto) {
        const textoFormateado = texto.replace(/\n/g, '<br>');
        document.getElementById("narration").innerHTML += '<p style="color: green; font-weight: bold;">' + textoFormateado + '</p>'; // Obtenemos el valor del textarea con el id pasado como argumento
}

document.addEventListener("DOMContentLoaded", init); // Esperamos a que el contenido de la página se haya cargado para ejecutar la función init{

function Personaje() {
    escribirTextoIA("\n CREACIÓN DE PERSONAJE (Cuanto más detalles, mejor saldrá la ilustración del personaje) \n");
    escribirTextoIA("Describe tu personaje (ej: Thorin, enano guerrero)\n");
}

function actualizarInventario(){
    get_inventario().then(resultado => {
        const inventario = resultado.inventario;
        const inventarioTexto = inventario.length > 0 ? inventario.map(item => "- " + item.nombre + ": " + item.descripcion).join("\n") : "Inventario vacío";
        const inventarioTextoFormateado = inventarioTexto.replace(/\n/g, '<br>');
        document.getElementById("inventory").innerHTML = '<p style="color: black; font-weight: bold;">' + " ----------INVENTARIO---------- <br><br>" + inventarioTextoFormateado + '</p>'; // Escribimos el inventario actualizado en el div
    }).catch(error => {
        console.error("Error al obtener el inventario:", error);
    });
}
function Campaña() {
    escribirTextoIA("\n\n CREACIÓN DE CAMPAÑA (Cuanto mejor sea la descripción, mejor saldrá la ilustración del lugar)\n");
    escribirTextoIA("¿Qué tipo de aventura quieres? (ej: mazmorra oscura, bosque maldito, ciudad pirata)\n");
}
function limpiarInput() {
    document.getElementById("prompt-input").value = "";
}
function limpiarNarracion(){
    document.getElementById("narration").innerHTML = "";
}

async function borrar() {
    await borrarPartida();
}