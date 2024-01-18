# gtfs-realtime
Implementación de GTFS Realtime

## Equipo de trabajo

- Edson Murillo
- Adrián Cordero

### Especificación del formato de transmisión de datos de telemetría

> "¿Cómo se van a transmitir los datos por la red desde los buses hasta el servidor en tiempo real?"

Esto es independiente de GTFS Realtime, en cuanto al formato. Debe incluir las variables deseadas en GTFS Realtime pero también contemplar todas las variables posibles para un sistema inteligente de transporte público, en general, según la referencia de ARC-IT o las necesidades del sistema en Costa Rica.

Según GTFS:

- Ubicación geográfica
- Dirección
- Velocidad
- Ocupación

Según ARC-IT:

- Presión de las llantas
- Etc.

Según necesidades específicas:

- Presión barométrica
- Contaminación del aire
- Etc.

(Ver issue #1)

### Recopilación de datos de telemetría para GTFS Realtime

> "¿Cuáles datos vamos a mostrar en el prototipo?"

Para nuestra implementación del prototipo, esto puede ser de varias formas:

- Con una implementación a escala real en conjunto con RACSA
- Con una implementación de prueba con una plataforma de desarrollo
- Con datos sintéticos generados para mostrar la visualización (_hardcoded_)

Es necesario revisar la plataforma para recolección de datos en tiempo real. Podría ser Apache Pulsar.

### Construcción y entrega del `FeedMessage` de GTFS Realtime

Un _script_ para tomar las variables de interés de GTFS Realtime y construir un archivo binario `.pb` para distribución (será recopilado por el proyecto `gtfs-screens`).

Seguir la secuencia: diccionario de Python --> JSON (publicación de cortesía) --> (paquete de Google que lo hace) --> Protobuf --> colocar en el servidor para ser recopilado.
