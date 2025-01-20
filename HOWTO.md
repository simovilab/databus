# Instrucciones de ejecución de la plataforma

El sistema requiere de:

- Django / Python
- PostgreSQL / PostGIS
- Celery / Celery Beat
- Redis

## Django

La plataforma de Django será útil para:

- Crear el sitio web con el panel de administración
- Administrar las tareas periódicas con su integración con Celery y Celery Beat
- Actualizar la información en tiempo real con las pantallas con WebSockets

Es necesario instalar Django 5.0 y la extensión Django Channels:

```bash
pip install django
pip install channels
```

## PostgreSQL / PostGIS

El proyecto requiere de una base de datos con una extensión para datos geoespaciales...

```bash
sudo apt install postgresql
(...)
sudo apt install postgis
```

Modificar `pg_hba.conf` de forma que sea:

```text
local    all    postgres   trust

local    all    all        trust
```
y así no tendrá contraseñas. Luego en la terminal:

```bash
sudo -u postgres psql
```

que nos lleva a la interfaz de `psql` para configurar un nuevo usuario:

```bash
postgres=# CREATE ROLE user_name SUPERUSER;
postgres=# ALTER ROLE user_name LOGIN;
```

Ahora podemos crear una base de datos, para este proyecto:

```bash
createdb realtime
```

ahora hay que ingresar a esa base de datos:

```bash
psql realtime
```

y ahí crear la extensión de PostGIS con:

```bash
realtime=# CREATE EXTENSION postgis;
```

Con esto quedaría lista la base de datos para conectarnos desde Django.

## Celery

Celery es un administrador de tareas (_task manager_)...

### Celery

Instalar Celery...

```bash
pip install version
```

y probar con `celery --version`.

Ejecutar Celery con:

```bash
celery -A realtime worker --loglevel=info
```

### Celery Beat

Celery utiliza los paquetes de integración con Django `django-celery-results` y `django-celery-beat`, y el intermediador de mensajes Redis.

```bash
celery -A realtime beat --scheduler django_celery_beat.schedulers:DatabaseScheduler --loglevel=info
```

## Redis

```bash
sudo apt install redis-server
```

Nota: en macOS:

```bash
brew install redis
```

Probar su estado como proceso del sistema:

```bash
sudo systemctl status redis-server
```

Probar la conexión:

```bash
>>> redis-cli ping
PONG
```

## Django Channels

Para habilitar la conexión permanente y bidireccional entre cliente y servidor con WebSockets, es necesario utilizar la extensión Django [Channels](https://channels.readthedocs.io/en/latest/), con [Daphne](https://github.com/django/daphne) como servidor HTTP/WebSocket (`http://`/`ws://`) y con [Redis](https://github.com/django/channels_redis) como intermediador de mensajes nuevamente. Para esto son necesarios los paquetes:

- `channels`
- `daphne`
- `redis`
- `channel-redis`

Este es un modo de conexión asíncrono, y por tanto requiere de la configuración ASGI (*Asynchronous Server Gateway Interface*). Esto se hace en el archivo `asgi.py`.

Similar a `urls.py`, Channels requiere un archivo `routing.py` donde establece los `websocket_urlpatterns`, es decir, las rutas o URLs donde se establece la conexión del WebSocket `ws://`.

También, similar a `views.py`, Channels define un archivo `consumers.py` donde define la lógica a realizar durante la conexión.

A diferencia de 

Al configurar `settings.py` con Daphne, el comando `python manage.py runserver` ahora ejecuta también ASGI. De hecho, ahora en la terminal se muestra:

```bash
Starting ASGI/Daphne version 4.1.0 development server at http://127.0.0.1:8000/
```
y toda la funcionalidad "regular" (WSGI) continúa operando.
