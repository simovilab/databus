# Especificación del equipo de abordo

!!! info
    Trabajo en desarrollo

Un equipo de abordo (**OBE**, del inglés *On-Board Equipment*) es una computadora/router ubicada en las unidades de autobús diseñadas para varias tareas, entre ellas:

- Recopilar datos del bus a través de sensores, como:
    - Ubicación, velocidad, dirección, con GPS y/o sensores inerciales
    - Ocupación del bus, con cámaras, barras u otros
    - Presión de llantas, puertas abiertas, etc.
    - Datos ambientales, con sensores de todo tipo
- Enviar alertas con *input* del operador del bus (choques, quedó varado, etc.)
- Operar como *router* Wi-Fi para pasajeros del bus
- Enviar periódicamente toda la información necesaria por medio de alguna red de acceso (celular o Wi-Fi, por ejemplo) a uno o varios servidores

## Requisitos

### Requisitos mínimos

- Sensor GPS
- Conectividad en red celular y/o Wi-Fi
- Interfaz para conductor

# Requisitos deseables

- Cámara para 
- Pantalla informativa para pasajeros

### Conectividad

Es deseable conectividad celular, con capacidades para solicitudes HTTP

## Especificación de los datos a enviar

Los datos serán enviados siguiendo la especificación de los datos del API...

### Interfaz

Tareas:

- Configurar el equipo para un vehículo
- Ingresar los datos de cada viaje

Ejemplo de secuencia de inicio de viaje:

1. [Botón de configurar nuevo viaje]
2. Seleccionar ruta del viaje
3. Seleccionar viaje, según hora (lista prestablecida en GTFS Schedule)
4. [Botón de iniciar viaje]
    - Al iniciar viaje, se registran la fecha y hora

