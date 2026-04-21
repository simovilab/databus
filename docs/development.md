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

## Posibles fuentes de datos

- Un _feed_ GTFS Realtime de alguna agencia (ejemplo: MBTA). Pros: ya están listos y accesibles. Contras: ya son GTFS Realtime (no incluye la transformación), son masivos y ajenos a nuestras pantallas.
- Datos sintéticos para pruebas. Pros: pueden diseñarse para ser un MWE (ejemplo viable mínimo) para nuestro contexto específico. Contras: no son realistas, requieren pensar dedicadamente en la "simulación".
  - _Hard-coded_
  - Simulación con [SUMO](https://eclipse.dev/sumo/). Nota: hay un proyecto con Gustavo Núñez que desarrolló algo como esto.
- Datos generados por un prototipo en la UCR (ejemplo: la implementación con RACSA). Pros: es el objetivo del proyecto. Contras: es laborioso y caro de implementar pues requiere de equipo de hardware y conexión a la red.

El consenso es iniciar con datos sintéticos de prueba.

## Datos sintéticos para pruebas del sistema

Hacer un *script* de creación de **datos sintéticos** donde podamos simular datos "en tiempo real" para desplegarlos en las pantallas.
 
- Posiblemente, crear un *toy model* para la prueba del prototipo, no necesariamente un modelo realista del sistema de la U, pero sí tiene que ser consistente con un GTFS Schedule.
- Considerar la aleatoriedad de los tiempos de desplazamiento y de la ocupación del bus. Para que tenga un realismo aceptable, debe ser coherente con, por ejemplo, los tiempos de subida y bajada de los pasajeros, etc.
- Como referencia, hay un proyecto en SUMO (simulador de redes de tránsito vehicular), preguntar a Gustavo Núñez.
- Los datos entre los buses son asincrónicos, es decir, llegan en cualquier momento, no están coordinados entre sí. Para que sea realista debe haber más de un bus (de preferencia muchos) circulando en cualquier momento dado.

Premisas para hacer un modelo simplificado:

- Utilizar el GTFS del bus UCR
- La pantalla objetivo está en Facultad de Ingeniería (la visualización sería ahí)
- Hacer salidas regulares de buses. Si un bus tarda aproximadamente de 20 a 30 minutos haciendo un viaje (depende de la trayectoria, con o sin "milla"), entonces con un tiempo de salida regular cada aproximadamente 15 minutos, siempre habría más de un bus reportando datos en el sistema. Esto es útil para probar la visualización. Dado el caso, sería posible modificar ese "headway" (tiempo entre salidas) para hacerlo menor o mayor y probar el sistema.
- Podemos asumir libremente que el sistema opera 24/7 con salidas regulares. Que no se nos olvide probar el caso en el que no hay datos (ejemplo: la pantalla debe tener un mensaje de que no hay buses actualmente o algo así).
- Elegir solamente los datos de GTFS Realtime (ocupación, velocidad, dirección, posición, odómetro) y *tal vez* algún dato complementario para enviar
- Simulación de datos:
  - Posición: elegir un punto de la secuencia de puntos de la trayectoria en la tabla `shapes.txt` basados en la distancia recorrida (`shape_dist_traveled`) y algún criterio de velocidad promedio del bus (por ejemplo 15 km/h para una trayectoria de 5 km recorrida en 20 minutos).
  - Velocidad: un número aleatorio elegido de una distribución normal con valor medio 15 km/h (u otra velocidad promedio) con una desviación estándar "sensata".
  - Ocupación: un número aleatorio entre 0 y C (capacidad máxima del bus) pero que cambia únicamente después de pasar por una parada. Para esto hay que conocer dónde están las paradas (tabla `stops.txt`). Mejor enfocar la aleatoriedad como: "se subieron o bajaron N personas en cada parada".
  - Dirección: la dirección del vector que une el punto de la trayectoria anterior con la posición actual, y según GTFS Realtime: "Bearing, in degrees, clockwise from True North, i.e., 0 is North and 90 is East."
  - Odómetro: distancia recorrida en el viaje, igual a `shape_dist_traveled`.
- Luego: crear el `FeedMessage` binaro del GTFS Realtime a partir de esto.
- Sugerencia: un _script_ para la creación de los datos simulados y otro _script_ para la conversión en GTFS Realtime (usar paquetes de Google para eso).

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

Nota mental:

- `VehiclePositions` se construye a partir de los datos de los buses
- `TripUpdates` se construye a partir de cálculos hechos en el servidor
- `ServiceAlerts` se construye a partir de *input* de una plataforma de interfaz con la administración del servicio

## Estructura del proyecto en Django

### Aplicaciones

- `gtfs`: maneja la base de datos con los datos GTFS
- `feed`: realiza las tareas periódicas de recolección de datos de los buses y la (futura) plataforma de `ServiceAlerts` para crear el `FeedMessage`.
- `website`: controla las páginas misceláneas del servidor como panel de administración y panel de datos, etc.