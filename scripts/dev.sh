#!/usr/bin/env bash
# Databús development environment startup script

set -euo pipefail

# Always run from the repo root, regardless of where the script is invoked from
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m'

COMPOSE_FILE="compose.dev.yml"

# ---------------------------------------------------------------------------
# Print a consistently formatted section title with a chosen color
# ---------------------------------------------------------------------------
print_section() {
    local color="$1"
    local title="$2"
    echo ""
    echo -e "${color}-----------------------------------------------------${NC}"
    echo -e "${color}  ${title}${NC}"
    echo -e "${color}-----------------------------------------------------${NC}"
}

# ---------------------------------------------------------------------------
# Read a value from .env / .env.dev (.env.dev overrides .env)
# ---------------------------------------------------------------------------
get_env_value() {
    local key="$1"
    local default_value="$2"
    local value dev_value

    value=$(grep -E "^${key}=" .env 2>/dev/null | tail -n1 | cut -d'=' -f2- || true)
    dev_value=$(grep -E "^${key}=" .env.dev 2>/dev/null | tail -n1 | cut -d'=' -f2- || true)
    [ -n "$dev_value" ] && value="$dev_value"
    echo "${value:-$default_value}"
}

BACKEND_PORT=$(get_env_value "BACKEND_PORT" "8000")
STATE_PORT=$(get_env_value "STATE_PORT" "6379")
MQTT_BROKER_PORT=$(get_env_value "MQTT_BROKER_PORT" "1883")
MESSAGE_BROKER_AMQP_PORT=$(get_env_value "MESSAGE_BROKER_AMQP_PORT" "5672")
MESSAGE_BROKER_MANAGEMENT_PORT=$(get_env_value "MESSAGE_BROKER_MANAGEMENT_PORT" "15672")
ANALYTICS_PORT=$(get_env_value "ANALYTICS_PORT" "4200")

echo -e "${GREEN}Databús — development environment${NC}"
echo ""

# ---------------------------------------------------------------------------
# Check dependencies
# ---------------------------------------------------------------------------

if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}Error: docker is not installed or not in PATH.${NC}"
    exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
    echo -e "${RED}Error: curl is not installed or not in PATH.${NC}"
    exit 1
fi

# Check required files
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found.${NC}"
    if [ -f ".env.example" ]; then
        echo "Copying .env.example -> .env ..."
        cp .env.example .env
        echo -e "${YELLOW}Edit .env with your values before continuing.${NC}"
    fi
    exit 1
fi
if [ ! -f ".env.dev" ]; then
    echo -e "${YELLOW}Warning: .env.dev not found. Using values from .env only.${NC}"
fi
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}Error: $COMPOSE_FILE not found.${NC}"
    exit 1
fi

# ---------------------------------------------------------------------------
# GTFS submodule
# ---------------------------------------------------------------------------

GTFS_DIR="backend/gtfs"
if [ ! -d "$GTFS_DIR" ] || [ -z "$(ls -A "$GTFS_DIR" 2>/dev/null)" ]; then
    echo -e "${YELLOW}Initializing GTFS submodule (${GTFS_DIR})...${NC}"
    if git submodule update --init --recursive; then
        echo -e "${GREEN}GTFS submodule ready.${NC}"
    else
        echo -e "${RED}Failed to initialize GTFS submodule.${NC}"
        echo "Try manually: git submodule update --init --recursive"
        exit 1
    fi
else
    echo -e "${GREEN}GTFS submodule already present at ${GTFS_DIR}.${NC}"
fi

# ---------------------------------------------------------------------------
# Pull base images (only services without a local build)
# ---------------------------------------------------------------------------

echo ""
echo -e "${BLUE}Pulling required Docker images...${NC}"
docker compose -f "$COMPOSE_FILE" pull --ignore-buildable

# ---------------------------------------------------------------------------
# Start services
# ---------------------------------------------------------------------------

echo ""
echo -e "${BLUE}Building and starting services...${NC}"
set +e
docker compose -f "$COMPOSE_FILE" up --build -d --remove-orphans
UP_EXIT=$?
set -e
if [ $UP_EXIT -ne 0 ]; then
    echo -e "${RED}Error: docker compose up failed (exit code ${UP_EXIT}).${NC}"
    echo -e "${YELLOW}Recent logs:${NC}"
    docker compose -f "$COMPOSE_FILE" logs --tail=30
    exit 1
fi

# ---------------------------------------------------------------------------
# Wait for orchestrator
# ---------------------------------------------------------------------------

echo ""
echo -e "${YELLOW}Waiting for orchestrator on: ${BACKEND_PORT}...${NC}"
echo -e "${GRAY}(First run may take 1-2 minutes while database extensions and Django setup run)${NC}"

MAX_WAIT=90
ELAPSED=0
ORCHESTRATOR_OK=false

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if curl -sf --max-time 3 "http://localhost:${BACKEND_PORT}" >/dev/null 2>&1; then
        ORCHESTRATOR_OK=true
        break
    fi

    # Every 15s: print container status + last orchestrator log lines
    if [ $(( ELAPSED % 15 )) -eq 0 ] && [ $ELAPSED -gt 0 ]; then
        echo ""
        echo -e "${GRAY}  [${ELAPSED}s] Containers:${NC}"
        docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null \
            | while IFS= read -r line; do echo -e "${GRAY}    ${line}${NC}"; done
        echo -e "${GRAY}  [${ELAPSED}s] Last orchestrator lines:${NC}"
        docker compose -f "$COMPOSE_FILE" logs --tail=5 orchestrator 2>/dev/null \
            | while IFS= read -r line; do echo -e "${GRAY}    ${line}${NC}"; done
    else
        echo -e "${GRAY}  . [${ELAPSED}s]${NC}"
    fi

    sleep 3
    ELAPSED=$(( ELAPSED + 3 ))
done

if [ "$ORCHESTRATOR_OK" = true ]; then
    echo ""
    echo -e "${GREEN}Orchestrator responding after ${ELAPSED}s.${NC}"
else
    echo ""
    echo -e "${RED}Orchestrator did not respond within ${MAX_WAIT}s.${NC}"
    echo -e "${YELLOW}Last orchestrator logs:${NC}"
    docker compose -f "$COMPOSE_FILE" logs --tail=30 orchestrator
fi

# ---------------------------------------------------------------------------
# Container status
# ---------------------------------------------------------------------------

print_section "$CYAN" "Container status"

docker compose -f "$COMPOSE_FILE" ps

# ---------------------------------------------------------------------------
# Infrastructure health checks
# ---------------------------------------------------------------------------

print_section "$CYAN" "Infrastructure health checks"

for svc in database state message-broker; do
    cid=$(docker compose -f "$COMPOSE_FILE" ps -q "$svc" 2>/dev/null || true)
    if [ -n "$cid" ]; then
        health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no healthcheck{{end}}' "$cid" 2>/dev/null || echo "unknown")
        status=$(docker inspect --format='{{.State.Status}}' "$cid" 2>/dev/null || echo "?")
        if [ "$health" = "healthy" ] || [ "$health" = "no healthcheck" ]; then
            echo -e "  ${GREEN}[OK]${NC}  ${svc}: ${status} / ${health}"
        else
            echo -e "  ${RED}[!!]${NC}  ${svc}: ${status} / ${health}"
        fi
    else
        echo -e "  ${RED}[!!]${NC}  ${svc}: container not found"
    fi
done

# ---------------------------------------------------------------------------
# Docker volumes
# ---------------------------------------------------------------------------

print_section "$CYAN" "Docker volumes"

# NOTE: If upgrading from an older PostgreSQL image, you must run
# `docker compose -f compose.dev.yml down -v` to remove the old database_data
# volume before starting fresh. PG18 is incompatible with data from PG15.
for vol in database_data state_data lake_data message_broker_data backend_venv; do
    full_name="databus-dev_${vol}"
    if docker volume inspect "$full_name" >/dev/null 2>&1; then
        mp=$(docker volume inspect --format='{{.Mountpoint}}' "$full_name" 2>/dev/null || echo "?")
        echo -e "  ${GREEN}[OK]${NC}  ${full_name}"
        echo    "        Mountpoint: ${mp}"
    else
        echo -e "  ${YELLOW}[--]${NC}  ${full_name}: does not exist yet (created on first use)"
    fi
done

# ---------------------------------------------------------------------------
# URLs and useful commands
# ---------------------------------------------------------------------------

print_section "$GREEN" "Development URLs"

echo "  Orchestrator / API   http://localhost:${BACKEND_PORT}"
echo "  Django admin         http://localhost:${BACKEND_PORT}/admin"
echo "  REST API             http://localhost:${BACKEND_PORT}/api/"
echo "  RabbitMQ management  http://localhost:${MESSAGE_BROKER_MANAGEMENT_PORT}"
echo "  Prefect (analytics)  http://localhost:${ANALYTICS_PORT}"

print_section "$BLUE" "Infrastructure ports"

echo "  PostgreSQL (database)   internal only (docker compose exec database psql -U postgres)"
echo "  Redis (state)        localhost:${STATE_PORT}"
echo "  MQTT (telemetry)     localhost:${MQTT_BROKER_PORT}"
echo "  RabbitMQ AMQP        localhost:${MESSAGE_BROKER_AMQP_PORT}"

print_section "$YELLOW" "Useful commands"

echo "  Stream logs:          docker compose -f $COMPOSE_FILE logs -f"
echo "  Orchestrator logs:    docker compose -f $COMPOSE_FILE logs -f orchestrator"
echo "  Run migrations:       docker compose -f $COMPOSE_FILE exec orchestrator uv run python manage.py migrate"
echo "  Create superuser:     docker compose -f $COMPOSE_FILE exec orchestrator uv run python manage.py createsuperuser"
echo "  Django shell:         docker compose -f $COMPOSE_FILE exec -it orchestrator uv run python manage.py shell"
echo "  Stop all:             docker compose -f $COMPOSE_FILE down"
echo ""
