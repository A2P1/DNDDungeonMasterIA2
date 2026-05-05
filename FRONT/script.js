import {obtenerPersonaje, crearPersonaje, obtenerCampaña, crearCampaña, borrarCampaña, iniciarCombate, obtenerEstadoCombate, accionCombate, obtenerInventario, usarItemInventario, añadirObjetoInventario, eliminarObjetoInventario, obtenerEstadoPartida, obtenerResumenPartida, accionPartida, iniciarPartida} from './api.js' ; // Importamos las funciones de la API para usarlas en el frontend


document.addEventListener('DOMContentLoaded', function() { // Esperamos a que el DOM esté cargado para ejecutar el código
    const texto = "HOLA";
    function escribirTexto(texto) {
        document.getElementById("narration").value += texto; // Obtenemos el valor del textarea con el id pasado como argumento
    }
    escribirTexto(texto); // Escribimos el texto de ejemplo en el textarea al cargar la página
});

