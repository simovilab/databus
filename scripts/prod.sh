#!/usr/bin/env bash
# Databús production environment startup script

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

COMPOSE_FILE="compose.prod.yml"

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
# Read a value from .env / .env.prod (.env.prod overrides .env)
# ---------------------------------------------------------------------------
get_env_value() {
    local key="$1"
    local default_value="$2"
    local value prod_value

    value=$(grep -E "^${key}=" .env 2>/dev/null | tail -n1 | cut -d'=' -f2- || true)
    prod_value=$(grep -E "^${key}=" .env.prod 2>/dev/null | tail -n1 | cut -d'=' -f2- || true)
    [ -n "$prod_value" ] && value="$prod_value"
    echo "${value:-$default_value}"
}

echo -e "${GREEN}Databús — production environment${NC}"
echo ""

# ---------------------------------------------------------------------------
# Check dependencies
# ---------------------------------------------------------------------------

if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}Error: docker is not installed or not in PATH.${NC}"
    exit 1
fi

# ---------------------------------------------------------------------------
# Check required files
# ---------------------------------------------------------------------------

if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found.${NC}"
    if [ -f ".env.example" ]; then
        echo "Copying .env.example -> .env ..."
        cp .env.example .env
        echo -e "${YELLOW}Edit .env with your production values before continuing.${NC}"
    fi
    exit 1
fi
if [ ! -f ".env.prod" ]; then
    echo -e "${RED}Error: .env.prod file not found.${NC}"
    exit 1
fi
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}Error: $COMPOSE_FILE not found.${NC}"
    exit 1
fi

# ---------------------------------------------------------------------------
# Validate required environment variables
# ---------------------------------------------------------------------------

print_section "$BLUE" "Validating environment"

MISSING=0
for var in ORCHESTRATOR_DOMAIN UI_DOMAIN MQTT_DOMAIN RABBITMQ_DOMAIN ANALYTICS_DOMAIN \
           FLOWER_DOMAIN DOCS_DOMAIN SECRET_KEY DB_PASSWORD REDIS_PASSWORD RABBITMQ_PASS; do
    val=$(get_env_value "$var" "")
    if [ -z "$val" ]; then
        echo -e "  ${RED}[MISSING]${NC}  $var"
        MISSING=$((MISSING + 1))
    else
        # Mask credentials, show domains
        case "$var" in
            *PASSWORD*|*PASS*|*SECRET*|*KEY*)
                echo -e "  ${GREEN}[OK]${NC}      $var = ****"
                ;;
            *)
                echo -e "  ${GREEN}[OK]${NC}      $var = $val"
                ;;
        esac
    fi
done

if [ $MISSING -gt 0 ]; then
    echo ""
    echo -e "${RED}Error: $MISSING required variable(s) not set. Fix .env / .env.prod and retry.${NC}"
    exit 1
fi

# ---------------------------------------------------------------------------
# Check Traefik network
# ---------------------------------------------------------------------------

if ! docker network inspect traefik_proxy >/dev/null 2>&1; then
    echo ""
    echo -e "${YELLOW}Traefik network 'traefik_proxy' not found. Creating it...${NC}"
    docker network create traefik_proxy
    echo -e "${GREEN}Created 'traefik_proxy' network.${NC}"
else
    echo ""
    echo -e "${GREEN}Traefik network 'traefik_proxy' exists.${NC}"
fi

# ---------------------------------------------------------------------------
# Validate compose configuration
# ---------------------------------------------------------------------------

print_section "$BLUE" "Validating compose configuration"

if docker compose -f "$COMPOSE_FILE" config --quiet 2>/dev/null; then
    echo -e "  ${GREEN}[OK]${NC}  $COMPOSE_FILE is valid"
else
    echo -e "  ${RED}[!!]${NC}  $COMPOSE_FILE has errors:"
    docker compose -f "$COMPOSE_FILE" config 2>&1 | head -20
    exit 1
fi

# ---------------------------------------------------------------------------
# Pull base images (only services without a local build)
# ---------------------------------------------------------------------------

print_section "$BLUE" "Pulling required Docker images"

docker compose -f "$COMPOSE_FILE" pull --ignore-buildable

# ---------------------------------------------------------------------------
# Build production images
# ---------------------------------------------------------------------------

print_section "$BLUE" "Building production images"

docker compose -f "$COMPOSE_FILE" build

# ---------------------------------------------------------------------------
# Start services (infrastructure first, then application)
# ---------------------------------------------------------------------------

print_section "$BLUE" "Starting infrastructure services"

docker compose -f "$COMPOSE_FILE" up -d database state message-broker

echo -e "${GRAY}Waiting for infrastructure to become healthy...${NC}"
MAX_WAIT=60
ELAPSED=0
INFRA_OK=false

while [ $ELAPSED -lt $MAX_WAIT ]; do
    ALL_HEALTHY=true
    for svc in database state message-broker; do
        cid=$(docker compose -f "$COMPOSE_FILE" ps -q "$svc" 2>/dev/null || true)
        if [ -n "$cid" ]; then
            health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no healthcheck{{end}}' "$cid" 2>/dev/null || echo "unknown")
            if [ "$health" != "healthy" ] && [ "$health" != "no healthcheck" ]; then
                ALL_HEALTHY=false
            fi
        else
            ALL_HEALTHY=false
        fi
    done

    if [ "$ALL_HEALTHY" = true ]; then
        INFRA_OK=true
        break
    fi

    echo -e "${GRAY}  . [${ELAPSED}s]${NC}"
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

if [ "$INFRA_OK" = true ]; then
    echo -e "${GREEN}Infrastructure healthy after ${ELAPSED}s.${NC}"
else
    echo -e "${RED}Infrastructure not healthy after ${MAX_WAIT}s. Continuing anyway...${NC}"
    for svc in database state message-broker; do
        cid=$(docker compose -f "$COMPOSE_FILE" ps -q "$svc" 2>/dev/null || true)
        if [ -n "$cid" ]; then
            health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no healthcheck{{end}}' "$cid" 2>/dev/null || echo "unknown")
            echo -e "  ${YELLOW}${svc}${NC}: $health"
        fi
    done
fi

print_section "$BLUE" "Starting application services"

docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

# ---------------------------------------------------------------------------
# Wait for orchestrator
# ---------------------------------------------------------------------------

ORCHESTRATOR_DOMAIN=$(get_env_value "ORCHESTRATOR_DOMAIN" "localhost")

echo ""
echo -e "${YELLOW}Waiting for orchestrator to start...${NC}"
echo -e "${GRAY}(First run may take 1-2 minutes while database setup and migrations run)${NC}"

MAX_WAIT=120
ELAPSED=0
ORCHESTRATOR_OK=false

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Check via container health rather than HTTP (no TLS certs locally)
    cid=$(docker compose -f "$COMPOSE_FILE" ps -q orchestrator 2>/dev/null || true)
    if [ -n "$cid" ]; then
        status=$(docker inspect --format='{{.State.Status}}' "$cid" 2>/dev/null || echo "unknown")
        if [ "$status" = "running" ]; then
            # Check if Daphne is listening by testing TCP inside the container
            if docker exec "$cid" sh -c 'exec 3<>/dev/tcp/localhost/8000' 2>/dev/null; then
                ORCHESTRATOR_OK=true
                break
            fi
        fi
    fi

    if [ $(( ELAPSED % 15 )) -eq 0 ] && [ $ELAPSED -gt 0 ]; then
        echo -e "${GRAY}  [${ELAPSED}s] Last orchestrator lines:${NC}"
        docker compose -f "$COMPOSE_FILE" logs --tail=3 orchestrator 2>/dev/null \
            | while IFS= read -r line; do echo -e "${GRAY}    ${line}${NC}"; done
    else
        echo -e "${GRAY}  . [${ELAPSED}s]${NC}"
    fi

    sleep 3
    ELAPSED=$((ELAPSED + 3))
done

if [ "$ORCHESTRATOR_OK" = true ]; then
    echo -e "${GREEN}Orchestrator responding after ${ELAPSED}s.${NC}"
else
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

for vol in database_data state_data message_broker_data backend_venv static_files; do
    full_name="databus-prod_${vol}"
    if docker volume inspect "$full_name" >/dev/null 2>&1; then
        echo -e "  ${GREEN}[OK]${NC}  ${full_name}"
    else
        echo -e "  ${YELLOW}[--]${NC}  ${full_name}: does not exist yet (created on first use)"
    fi
done

# ---------------------------------------------------------------------------
# Production URLs and domains
# ---------------------------------------------------------------------------

UI_DOMAIN=$(get_env_value "UI_DOMAIN" "")
MQTT_DOMAIN=$(get_env_value "MQTT_DOMAIN" "")
RABBITMQ_DOMAIN=$(get_env_value "RABBITMQ_DOMAIN" "")
ANALYTICS_DOMAIN=$(get_env_value "ANALYTICS_DOMAIN" "")
FLOWER_DOMAIN=$(get_env_value "FLOWER_DOMAIN" "")
DOCS_DOMAIN=$(get_env_value "DOCS_DOMAIN" "")

print_section "$GREEN" "Production URLs (via Traefik)"

echo "  Orchestrator / API   https://${ORCHESTRATOR_DOMAIN}"
echo "  Django admin         https://${ORCHESTRATOR_DOMAIN}/admin"
echo "  REST API             https://${ORCHESTRATOR_DOMAIN}/api/"
echo "  Frontend             https://${UI_DOMAIN}"
echo "  Documentation        https://${DOCS_DOMAIN}"
echo "  MQTT (TLS)           mqtts://${MQTT_DOMAIN}:8883"
echo "  RabbitMQ management  https://${RABBITMQ_DOMAIN}"
echo "  Prefect (analytics)  https://${ANALYTICS_DOMAIN}"
echo "  Flower (monitoring)  https://${FLOWER_DOMAIN}"

print_section "$YELLOW" "Useful commands"

echo "  Stream logs:          docker compose -f $COMPOSE_FILE logs -f"
echo "  Orchestrator logs:    docker compose -f $COMPOSE_FILE logs -f orchestrator"
echo "  Run migrations:       docker compose -f $COMPOSE_FILE exec orchestrator uv run python manage.py migrate"
echo "  Create superuser:     docker compose -f $COMPOSE_FILE exec orchestrator uv run python manage.py createsuperuser"
echo "  Collect static:       docker compose -f $COMPOSE_FILE exec orchestrator uv run python manage.py collectstatic"
echo "  Rebuild & restart:    docker compose -f $COMPOSE_FILE build && docker compose -f $COMPOSE_FILE up -d"
echo "  Stop all:             docker compose -f $COMPOSE_FILE down"
echo ""