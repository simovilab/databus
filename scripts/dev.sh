#!/usr/bin/env bash
# Development environment startup script for Infobús

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

COMPOSE_FILE="compose.dev.yml"

get_env_value() {
    local key="$1"
    local default_value="$2"
    local value

    # .env.dev overrides .env; check base file first, then let dev file win
    value=$(grep -E "^${key}=" .env 2>/dev/null | tail -n 1 | cut -d '=' -f 2- || true)
    local dev_value
    dev_value=$(grep -E "^${key}=" .env.dev 2>/dev/null | tail -n 1 | cut -d '=' -f 2- || true)
    if [ -n "$dev_value" ]; then
        value="$dev_value"
    fi

    if [ -n "$value" ]; then
        echo "$value"
    else
        echo "$default_value"
    fi
}

BACKEND_PORT=$(get_env_value "BACKEND_PORT" "8000")
DATABASE_PORT=$(get_env_value "DATABASE_PORT" "5432")
MEMORY_PORT=$(get_env_value "MEMORY_PORT" "6379")
CONTEXT_PORT=$(get_env_value "CONTEXT_PORT" "3278")
KNOWLEDGE_PORT=$(get_env_value "KNOWLEDGE_PORT" "3030")
BROKER_MANAGEMENT_PORT=$(get_env_value "BROKER_MANAGEMENT_PORT" "15672")
DEBUG=$(get_env_value "DEBUG" "true")

echo -e "${GREEN}🚀 Starting Infobús in DEVELOPMENT mode...${NC}"
echo "Features enabled:"
echo "  - Debug mode"
echo "  - Volume mounting for code changes"
echo ""

if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}❌ Error: docker is not installed or not in PATH.${NC}"
    exit 1
fi

# Check for necessary files
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env file not found!${NC}"
    echo "Please create .env with base configuration."
    echo "Creating .env from example..."
    cp .env.example .env
    exit 1
fi
if [ ! -f ".env.dev" ]; then
    echo -e "${YELLOW}⚠️  Warning: .env.dev file not found!${NC}"
fi
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}❌ Error: $COMPOSE_FILE file not found!${NC}"
    echo "Please create $COMPOSE_FILE for the development environment."
    exit 1
fi

echo -e "${BLUE}🔧 Building development environment...${NC}"

# Try to add the GTFS submodule if not present
if [ ! -d "gtfs" ] || [ -z "$(ls -A gtfs 2>/dev/null)" ]; then
    echo -e "${YELLOW}📦 Initializing GTFS submodule (gtfs-django)...${NC}"
    if git submodule update --init --recursive; then
        echo -e "${GREEN} GTFS submodule ready.${NC}"
    else
        echo -e "${RED} Failed to initialize GTFS submodule.${NC}"
        echo "Please ensure you have network access and try: git submodule update --init --recursive, or verify the submodule URL in .gitmodules"
        exit 1
    fi
fi

# Use compose.dev.yml for the development environment.
# Docker Compose loads .env for variable substitution; services also load env_file entries.

# --------------------------------------------------------------
docker compose -f "$COMPOSE_FILE" up --build -d --remove-orphans
# --------------------------------------------------------------

echo ""
echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"

until curl -s "http://localhost:${BACKEND_PORT}" >/dev/null; do
  sleep 2
done

echo -e "${GREEN}Backend is responding.${NC}"

# Check if services are running
echo -e "${BLUE}🏥 Checking service status...${NC}"
if docker compose -f "$COMPOSE_FILE" ps --status running | grep -q .; then
    echo -e "${GREEN}✅ Development environment started successfully!${NC}"
else
    echo -e "${RED}⚠️  Some services may not be running properly. Check logs for details.${NC}"
    echo -e "${YELLOW}📜 Showing recent logs...${NC}"
    docker compose -f "$COMPOSE_FILE" logs --tail=50
fi

docker compose -f "$COMPOSE_FILE" ps

echo ""
echo -e "${GREEN}🌐 Development URLs:${NC}"
echo "  Website: http://localhost:${BACKEND_PORT}"
echo "  Admin: http://localhost:${BACKEND_PORT}/admin"
echo "  API: http://localhost:${BACKEND_PORT}/api/"
echo "  Context service: http://localhost:${CONTEXT_PORT}"
echo "  Knowledge service: http://localhost:${KNOWLEDGE_PORT}"
echo "  RabbitMQ management: http://localhost:${BROKER_MANAGEMENT_PORT}"
echo ""
echo -e "${BLUE}📊 Service endpoints:${NC}"
echo "  Database: localhost:${DATABASE_PORT}"
echo "  Redis: localhost:${MEMORY_PORT}"
echo ""
echo -e "${YELLOW}🔧 Development commands:${NC}"
echo "  View logs: docker compose -f $COMPOSE_FILE logs -f"
echo "  View backend logs: docker compose -f $COMPOSE_FILE logs -f backend"
echo "  Run migrations: docker compose -f $COMPOSE_FILE exec backend uv run python manage.py migrate"
echo "  Create superuser: docker compose -f $COMPOSE_FILE exec backend uv run python manage.py createsuperuser"
echo "  Django shell: docker compose -f -it $COMPOSE_FILE exec backend uv run python manage.py shell"
echo ""
echo -e "${BLUE}To stop: docker compose -f $COMPOSE_FILE down${NC}"
