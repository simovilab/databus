# Enable a Development Environment with Docker

This document describes how to configure and run a development environment for `databus` using Docker.

> [!WARNING]
> It is ideal not to skip steps in this guide, and if necessary, ask for help.

> [!TIP]
> After completing this manual, it is recommended to take a look at the documents inside the `docs` folder to get familiar with the project and its components.

## Prerequisites

### Windows

The following components must be installed:

- [Windows Subsystem Linux](https://learn.microsoft.com/en-us/windows/wsl/setup/environment)
- [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)
- [Git](https://git-scm.com/downloads)

### UNIX-based Operating Systems (MacOS and Linux distributions)

The following components must be installed (it is recommended to check the specific documentation for your OS):

- [Python 3](https://www.python.org/)
- [Docker](https://www.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- [Git](https://git-scm.com/downloads)

> [!TIP]
> Installing [Docker Desktop](https://docs.docker.com/desktop/) includes the Docker engine and Docker Compose. It helps visualize containers and provides multiple useful tools.

## Steps to Follow Before Starting the Container

### 1. Clone the Repository

```bash
git clone https://github.com/simovilab/databus.git
```

### 2. Create Environment Variables File

Before starting the environment, you need to create a `.env.local` file at the root of the project. This file contains sensitive variables such as secret keys and database credentials.

> [!IMPORTANT]
> The `.env.local` file **must not be uploaded** to the repository. Request the content from another project collaborator.

> [!NOTE]
> The file [`.env.local.example`](.env.example) contains the fields that need to be filled in.

### 3. Grant Permissions to Scripts

Ensure the scripts are executable:

```bash
chmod +x ./scripts/*.sh
```

## Build and Run the Containers

### 1. Run Docker Desktop

Open the Docker Desktop executable application.

### 2. Build and Start All Services

Build and start all containers in detached mode:

```bash
docker-compose up -d --build
```

This command will:
- Build the Docker images
- Start PostgreSQL, Redis, Django web server, Celery worker, and Celery beat
- Run in the background (detached mode)

> [!NOTE]
> The first build may take several minutes. Subsequent builds will be faster.

### 3. Check Container Status

Verify all containers are running:

```bash
docker-compose ps
```

### 4. View Logs

View logs from all services:

```bash
docker-compose logs -f
```

Or view logs from a specific service:

```bash
docker-compose logs -f web
```

## Apply Migrations and Create Superuser

### Apply Database Migrations

Run migrations inside the container:

```bash
docker-compose exec web python manage.py migrate
```

Or use the helper script:

```bash
docker-compose exec web ./scripts/migrate.sh
```

### Create a Superuser

Create an admin user interactively:

```bash
docker-compose exec web python manage.py createsuperuser
```

Or use the helper script:

```bash
docker-compose exec web ./scripts/superuser.sh
```

Follow the prompts to enter username, email, and password.

## Run Tests

Run the test suite inside the container:

```bash
docker-compose exec web python manage.py test
```

Or use the helper script:

```bash
docker-compose exec web ./scripts/test.sh
```

## Stop and Clean Up Containers

### Stop All Containers

Stop all running containers without removing them:

```bash
docker-compose stop
```

### Stop and Remove Containers

Stop and remove all containers:

```bash
docker-compose down
```

### Stop, Remove Containers, and Delete Volumes

Stop containers and remove all data (including database):

```bash
docker-compose down -v
```

> [!WARNING]
> Using `-v` flag will delete all data in PostgreSQL and Redis. Use with caution!

### Remove Everything (Containers, Volumes, and Images)

```bash
docker-compose down -v --rmi all
```

## Access the Application

Once everything is running, access the application in your browser:

```
http://localhost:8000/
```

Access the Django admin panel:

```
http://localhost:8000/admin/
```

## Common Issues

### Container Fails to Start

- Verify that Docker is running correctly
- Ensure that the `.env` file is present and properly configured
- Check if ports 8000, 5432, or 6379 are already in use
- Try rebuilding the containers:

```bash
docker-compose down -v
docker-compose up -d --build
```

### Database Connection Errors

- Ensure PostgreSQL container is healthy:

```bash
docker-compose ps db
```

- Check database logs:

```bash
docker-compose logs db
```

- Verify environment variables in `.env` file match the database service configuration

### Permission Denied in the Docker Console

- Restart the docker containers:

```bash
docker-compose restart
```

### Changes Not Reflected in Container

If you modify `Dockerfile`, `requirements.txt`, or other build files, rebuild the containers:

```bash
docker-compose up -d --build
```

## Other Useful Commands

### Restart a Specific Service

```bash
docker-compose restart web
```

### Execute Commands in a Running Container

```bash
docker-compose exec web bash
```

### View Real-Time Logs

View logs from all services:

```bash
docker-compose logs -f
```

View logs from a specific service:

```bash
docker-compose logs -f web
```

### Rebuild a Single Service

```bash
docker-compose up -d --build web
```

### List All Containers

```bash
docker-compose ps
```

### Check Container Resource Usage

```bash
docker stats
```

## Using the Telemetry Simulator

The telemetry simulator allows you to test the system before installing equipment on real buses. It generates simulated tracking and telemetry data.

### Setup Simulator

1. **Apply migrations for simulator app**:

```bash
docker-compose exec web python manage.py makemigrations simulator
docker-compose exec web python manage.py migrate simulator
```

2. **Ensure you have GTFS data loaded** (routes, trips, stops, shapes)

3. **Create at least one operator** in the admin panel

### Start Simulation

Start simulation for all vehicles:

```bash
docker-compose exec web python manage.py start_simulation --all
```

Start simulation for a specific vehicle:

```bash
docker-compose exec web python manage.py start_simulation --vehicle SJB9876
```

Start with custom speed (m/s):

```bash
docker-compose exec web python manage.py start_simulation --vehicle SJB9876 --speed 15.0
```

### Monitor Simulation

- Access admin panel: `http://localhost:8000/admin/simulator/`
- View simulated vehicles and their status
- Check simulation logs for events and errors

### Stop Simulation

Stop all simulations:

```bash
docker-compose exec web python manage.py stop_simulation --all
```

Stop specific vehicle:

```bash
docker-compose exec web python manage.py stop_simulation --vehicle SJB9876
```

### How It Works

1. **Position updates**: Every 10 seconds (configurable)
2. **Occupancy updates**: When arriving at stops
3. **Automatic journey management**: Starts trips, follows routes, completes journeys

> [!NOTE]
> For detailed simulator documentation, see [`docs/simulator.md`](docs/simulator.md)

