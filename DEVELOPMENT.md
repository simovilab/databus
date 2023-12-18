# Desarrollo funcional

## Especificación de los datos

Investigar y proponer una **especificación de los datos** de telemetría (?) recopilados de los buses y transmitidos al servidor.

- Esto será parte de nuestra propuesta de arquitectura tecnológica.
- Preliminarmente, estará inspirado en NGSI-LD para la especificación de los datos recopilados, posiblemente con JSON-LD como formato.
- La decisión de cuáles datos recopilar puede estar basada en ARC-IT (según los distintos paquetes de servicio).
- No está limitado a los datos disponibles en GTFS Realtime.
- También puede depender de las necesidades operativa de las agencias de transporte (por ejemplo: hasta la presión de las llantas puede ser un dato a enviar).
- A veces no podemos ser exhaustivos en la lista de variables pero sí podemos hacer una clasificación sensata de grandes categorías donde están esos datos.
- Asumir que para nuestro prototipo vamos a probar con datos sintéticos creados con esta especificación.

## Datos sintéticos para pruebas del sistema

Hacer un *script* de creación de **datos sintéticos** donde podamos simular datos "en tiempo real" para desplegarlos en las pantallas
 
- Posiblemente, crear un *toy model* para la prueba del prototipo, no necesariamente un modelo realista del sistema de la U, pero sí tiene que ser consistente con un GTFS Schedule.
- Considerar la aleatoriedad de los tiempos de desplazamiento y de la ocupación del bus. Para que tenga un realismo aceptable, debe ser coherente con, por ejemplo, los tiempos de subida y bajada de los pasajeros, etc.
- Como referencia, hay un proyecto en SUMO (simulador de redes de tránsito vehicular), preguntar a Gustavo Núñez.
- Los datos entre los buses son asincrónicos, es decir, llegan en cualquier momento, no están coordinados entre sí. Para que sea realista debe haber más de un bus (de preferencia muchos) circulando en cualquier momento dado.

## Creación de GTFS Realtime

Crear un *script* de Python para recopilar los datos enviados según la especificación propuesta (arriba) y "confeccionar" un `FeedMessage` y dejar a disposición de todos los consumidores (incluyendo el otro servidor `gtfs-screens`).

Es necesario **dominar** [GTFS Realtime](https://gtfs.org/realtime/reference/) a profundidad. Un `FeedMessage` tiene tres posibles *entidades*:

- *Service Alerts*
- *Trip Updates*
- *Vehicle Positions*

> GTFS Realtime es entregado como un archivo binario Protobuf `.pb`. Referencia de [MBTA GTFS Realtime](https://github.com/mbta/gtfs-documentation/blob/master/reference/gtfs-realtime.md) para ver las actualizaciones (también disponibles en JSON).

En este proyecto, implementaremos *Vehicle Positions* y *Trip Updates*. *Service Alerts* no porque requiere de un sistema conectado con la agencia para que sea actualizado por personas, no es telemetría automatizada.

Secuencia prevista de esta tarea:

- Con algún mecanismo de recepción de datos en tiempo real (por ejemplo: Apache Pulsar) es necesario recopilar los datos y guardarlos en memoria.
- Cada $N$ segundos es necesario crear el `FeedMessage`. Inicialmente, $N = 20$ (esta es una importante referencia también para los datos sintéticos).
- Es necesario "desempacar" estos datos y crear la entidad `vehicle` de GTFS Realtime dentro de `FeedMessage`.
- Finalmente, dejar el archivo `.pb` y quizá `.json` en una URL, por ejemplo: `buses.ucr.ac.cr/realtime/vehicle_positions.pb`.
- Repetir *ad infinitum*
