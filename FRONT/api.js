//Declaro la función _fetch que se encargará de realizar las solicitudes HTTP

url = 'http://localhost:8000/api/'; // URL base de la API
async function _fetch(url, HTTPmethod, body) {
    const options = {
        method: HTTPmethod, // Tipo de petición HTTP (GET, POST, PUT, DELETE)
        headers: {
            'Content-Type': 'application/json' //  Espeficica que el cuerpo es un JSON
        },
        body: JSON.stringify(body) // Convierte el objeto a un string para enviarlo al back
    };
    const response = await fetch(url, options); // Esperamos una respuesta del servidor
    if (response.status === 204) { // Si la respuesta no tiene contenido, lanza un null
        return null;
    }
    if (!response.ok) // Lanza una alerta si hubo algún tipo de error
    {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Error en la solicitud');
    }
    else // Si todo ha ido bien, devuelve la respuesta en formato JSON
        return response.json();
}

// FUNCIONES DE PERSONAJE
async function obtenerPersonaje() { // Función para obtener al personaje
    return _fetch(url + '/personaje/', 'GET'); // Le pasamos la URL completa y el método de obtener
}

async function crearPersonaje(descripcion) { // Función para crear el personaje
    return _fetch(url + '/personaje/', 'POST', {descripcion : descripcion}); // Le pasamos la url, el método y el par clave-valor de la descripción del personaje
}

// FUNCIONES DE CAMPAÑA
async function obtenerCampaña() { // Función para obtener la campaña
    return _fetch(url + '/campaña/', 'GET'); // Le pasamos la URL completa y el método de obtener
}

async function crearCampaña(tema, personaje) {
    return _fetch(url + '/campaña/', 'POST', {tema : tema, personaje : personaje}); // Le pasamos la url, el método y el par clave-valor del tema y el personaje de la campaña
}

async function borrarCampaña(){
    return _fetch(url + '/campaña/', 'DELETE'); // Borramos la campaña
}

// FUNCIONES DE COMBATE

async function iniciarCombate() {
    return _fetch(url + '/combate/iniciar/', 'POST'); 
}

async function obtenerEstadoCombate(beat_id) {
    return _fetch(url + '/combate/estado/' + '?' + 'beat_id=' + beat_id, 'GET'); // Le pasamos la URL completa y el método de obtener
}

async function accionCombate(beat_id, accion) {
    return _fetch(url + '/combate/accion/', 'POST', {beat_id : beat_id, accion : accion}); // Le pasamos la url, el método y el par clave-valor del beat_id y la acción a realizar en el combate
}

// FUNCIONES DE INVENTARIO

async function obtenerInventario() {
    return _fetch(url + '/inventario/', 'GET'); // Le pasamos la URL completa y el método de obtener
}

async function usarItemInventario(nombre) {
    return _fetch(url + '/inventario/usar/', 'POST', {nombre : nombre});
}

async function añadirObjetoInventario(nombre, tipo, dado_daño, descripcion) {
    return _fetch(url + '/inventario/objeto/', 'POST', {nombre : nombre, tipo : tipo, dado_daño : dado_daño, descripcion : descripcion}); // Le pasamos la url, el método y el par clave-valor del nombre, tipo, dado de daño y descripción del objeto a añadir al inventario
}

async function eliminarObjetoInventario(nombre) {
    return _fetch(url + '/inventario/objeto/' + encodeURIComponent(nombre), 'DELETE'); // Le pasamos la url, el método y el par clave-valor del nombre del objeto a eliminar del inventario
}

// FUNCIONES PARTIDA

async function obtenerEstadoPartida(beat_actual, resumen, campaña_completada) {
    return _fetch(url + '/partida/estado/', 'GET', {beat_actual : beat_actual, resumen : resumen, campaña_completada : campaña_completada}); // Le pasamos la url, el método y el par clave-valor del beat actual, el resumen de la partida y si la campaña ha sido completada o no
}

async function obtenerResumenPartida() {
    return _fetch(url + '/partida/resumen/', 'GET'); // Le pasamos la URL completa y el método de obtener
}

async function accionPartida(accion) {
    return _fetch(url + '/partida/accion/', 'POST', {accion : accion}); // Le pasamos la url, el método y el par clave-valor de la acción a realizar en la partida
}

async function iniciarPartida() {
    return _fetch(url + '/partida/iniciar/', 'POST');
}
export {obtenerPersonaje, crearPersonaje, obtenerCampaña, crearCampaña, borrarCampaña, iniciarCombate, obtenerEstadoCombate, accionCombate, obtenerInventario, usarItemInventario, añadirObjetoInventario, eliminarObjetoInventario};