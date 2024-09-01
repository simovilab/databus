# Deployment

On a Linux Ubuntu 22.04 LTS server, this is the configuration of Celery and Celery Beat with `systemd`, following most of the instructions in the [Daemonization guide](https://docs.celeryq.dev/en/stable/userguide/daemonizing.html#daemon-systemd-generic) of Celery.

- **Note**: this assumes that Redis is installed (`sudo apt install redis-server`) and all the Python packages in `requirements.txt`. It is possible to check if Redis is running with `sudo systemctl is-enabled redis-server`.

## Configuring Celery as a system service

Preliminaries:

- The Django project is in `/home/bucr/realtime`
- The virtual environment is in `/home/bucr/realtime/realtimeenv/bin`
- The user is `bucr` and belongs to the group `bucr`

The environment variables are located in the file `/etc/conf.d/celery`, as shown below.

```ini title="/etc/conf.d/celery"
# Name of nodes to start
CELERYD_NODES="w1"

# Absolute or relative path to the 'celery' command:
CELERY_BIN="/home/bucr/realtime/realtimeenv/bin/celery"

# App instance to use
CELERY_APP="realtime"

# How to call manage.py
CELERYD_MULTI="multi"

# Extra command-line arguments to the worker
CELERYD_OPTS="--time-limit=300 --concurrency=1"

# - %n will be replaced with the first part of the nodename.
# - %I will be replaced with the current child process index
#   and is important when using the prefork pool to avoid race conditions.
CELERYD_PID_FILE="/var/run/celery/%n.pid"
CELERYD_LOG_FILE="/var/log/celery/%n%I.log"
CELERYD_LOG_LEVEL="INFO"

# Celery Beat
CELERYBEAT_SCHEDULER="django_celery_beat.schedulers:DatabaseScheduler"
CELERYBEAT_PID_FILE="/var/run/celery/beat.pid"
CELERYBEAT_LOG_FILE="/var/log/celery/beat.log"
```

Notes:

- Concurrency is set to 1 because current servers have single CPU(s), thread(s) per core and core(s) per socket.
- The directories `/var/run/celery/` and `/var/log/celery/` for the PID and LOG files, respectively, must first be created when configuring Celery. So:

```bash
sudo mkdir -p /var/run/celery/
sudo mkdir -p /var/log/celery/
```

- Now the user and group `bucr:bucr` need permissions for those directories:

```bash
sudo chown bucr:bucr /var/run/celery/
sudo chown bucr:bucr /var/log/celery/
```

- The PID file and log file must be created on each reboot with the following configuration, where `bucr bucr` is the user and group and `0755` are the permissions.

```ini title="/etc/tmpfiles.d/celery.conf"
d /run/celery 0755 bucr bucr -
d /var/log/celery 0755 bucr bucr -
```

### Celery Worker

This process is configured below.

```ini title="/etc/systemd/system/celery.service"
[Unit]
Description=Celery Service
After=network.target

[Service]
Type=forking
User=bucr
Group=bucr
EnvironmentFile=/etc/conf.d/celery
WorkingDirectory=/home/bucr/realtime/
RuntimeDirectory=celery
ExecStart=/bin/sh -c '${CELERY_BIN} -A $CELERY_APP multi start $CELERYD_NODES \
    --pidfile=${CELERYD_PID_FILE} \
    --logfile=${CELERYD_LOG_FILE} \
    --loglevel="${CELERYD_LOG_LEVEL}" \
    $CELERYD_OPTS'
ExecStop=/bin/sh -c '${CELERY_BIN} multi stopwait $CELERYD_NODES \
    --pidfile=${CELERYD_PID_FILE} \
    --logfile=${CELERYD_LOG_FILE} \
    --loglevel="${CELERYD_LOG_LEVEL}"'
ExecReload=/bin/sh -c '${CELERY_BIN} -A $CELERY_APP multi restart $CELERYD_NODES \
    --pidfile=${CELERYD_PID_FILE} \
    --logfile=${CELERYD_LOG_FILE} \
    --loglevel="${CELERYD_LOG_LEVEL}" \
    $CELERYD_OPTS'
Restart=always

[Install]
WantedBy=multi-user.target
```

Relevant `systemctl` commands:

- On every change to this file: `sudo systemctl daemon-reload`
- To start: `sudo systemctl start celery`
- To stop: `sudo systemctl stop celery`
- To check status: `sudo systemctl status celery`
- To allow execution on reboot: `sudo systemctl enable celery`
- Others: `restart`/`reload`/`is-enabled`/`disable`

### Celery Beat

This process is configured below.

- **Note**: the periodic tasks are configured in the Django admin panel, thanks to the package `django-celery-beat`, and as configured here with `--scheduler` as `django_celery_beat.schedulers:DatabaseScheduler`.

```ini title="/etc/systemd/system/celerybeat.service"
[Unit]
Description=Celery Beat Service
After=network.target celery.service

[Service]
Type=simple
User=bucr
Group=bucr
EnvironmentFile=/etc/conf.d/celery
WorkingDirectory=/home/bucr/realtime/
ExecStart=/bin/sh -c '${CELERY_BIN} -A ${CELERY_APP} beat \
    --pidfile=${CELERYBEAT_PID_FILE} \
    --logfile=${CELERYBEAT_LOG_FILE} \
    --loglevel=${CELERYD_LOG_LEVEL} \
    --scheduler ${CELERYBEAT_SCHEDULER}'
Restart=always

[Install]
WantedBy=multi-user.target
```

Relevant `systemctl` commands:

- On every change to this file: `sudo systemctl daemon-reload`
- To start: `sudo systemctl start celerybeat`
- To stop: `sudo systemctl stop celerybeat`
- To check status: `sudo systemctl status celerybeat`
- To allow execution on reboot: `sudo systemctl enable celery`
- Others: `restart`/`reload`/`is-enabled`/`disable`

