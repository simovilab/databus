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

Before starting the environment, you need to create a `.env` file at the root of the project. This file contains sensitive variables such as secret keys and database credentials.

> [!IMPORTANT]
> The `.env.` file **must not be uploaded** to the repository. Request the content from another project collaborator.


### 3. Grant Permissions to Scripts

Ensure the scripts are executable:

```bash
chmod +x ./scripts/*.sh
```

## Start the Container with the Development Environment

### 1. Run Docker Desktop:

Open the Docker Desktop executable application.

### 2. Run the Scripts

Run the script from the root:

```bash
./scripts/dev.sh
```

> [!NOTE]
> It is normal to see several warnings during this process.
> This process may take several minutes, be patient until it says "database is ready to accept connections"

## Access the Application

Once everything is running, access the browser with the following address, which by default is port 8000:

```
http://localhost:8000/
```

## Common Issues

### Permission Denied in the Docker Console
- Restart the docker container with

```bash
./scripts/dev.sh
```

### The Container Does Not Start or Fails During Installation

- Verify that Docker is running correctly.
- Ensure that the `.env` file is present and properly configured.
- If changes are made to the `Docker/Dockerfile` or dependencies, run:

```bash
docker compose down
docker compose up --build
```

## Other Useful Commands

### Stop the Environment

```bash
docker compose down
```

### View Real-Time Logs

```bash
docker compose logs -f
```
