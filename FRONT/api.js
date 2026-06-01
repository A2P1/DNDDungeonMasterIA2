//Declaro la función _fetch que se encargará de realizar las solicitudes HTTP

const url = 'http://localhost:8000'; // URL base de la API (sin barra final)
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


async function get_campaña() {
    return _fetch(url + '/campaña', 'GET'); // Le pasamos la URL completa y el método de obtener
}

async function get_inventario(){
    return _fetch(url + '/campaña/inventario', 'GET'); // Le pasamos la URL completa y el método de obtener
}
async function iniciarPartida(tema, personaje) {
    return _fetch(url + '/campaña/iniciar', 'POST', {tema: tema, personaje: personaje}); // Le pasamos la URL completa y el método de obtener
}

async function accionPartida(accion) {
    return _fetch(url + '/partida/accion', 'POST', {accion : accion}); // Le pasamos la url, el método y el par clave-valor de la acción a realizar en la partida
}

async function borrarPartida() {
    return _fetch(url + '/campaña/', 'DELETE'); // Borramos la campaña
}

async function accionCombate(beat_id, accion) {
    return _fetch(url + '/combate/conflicto', 'POST', {beat_id : beat_id, accion : accion}); // Le pasamos la url, el método y el par clave-valor del beat_id y la acción a realizar en el combate
}

export { get_campaña, iniciarPartida, accionPartida, borrarPartida, accionCombate, get_inventario }; // Exportamos las funciones para usarlas en el frontend