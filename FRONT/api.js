//Declaro la función _fetch que se encargará de realizar las solicitudes HTTP
async function _fetch(url, HTTPmethod, body) {
    const options = {
        method: HTTPmethod, // Tipo de petición HTTP (GET, POST, PUT, DELETE)
        headers: {
            'Content-Type': 'application/json' //  Espeficica que el cuerpo es un JSON
        },
        body: JSON.stringify(body) // Convierte el objeto a un string para enviarlo al back
    };
    const response = await fetch(url, options); // Esperamos una respuesta del servidor
    if (response.status === 204) { // Si la respuesta no tiene contenido, lanza un error de no contenido
        return null;
    }
    if (response.ok == false) // Lanza una alerta si hubo algún tipo de error
    {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Error en la solicitud');
    }
    else // Si todo ha ido bien, devuelve la respuesta en formato JSON
        return response.json();
}
