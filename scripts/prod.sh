#!/bin/bash
# Production environment startup script for Databus (containers)
# WARNING: This script has not been tested in real production environment since secret key is not available
set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🏭 Starting Databus in PRODUCTION mode...${NC}"
echo "Features enabled:"
echo "  - Nginx reverse proxy"
echo "  - Daphne ASGI server"
echo "  - Django Channels support"
echo "  - Static file caching"
echo "  - Security headers"
echo "  - Rate limiting"
echo "  - Optimized performance"
echo "  - PostGIS support"
echo ""

for f in .env .env.prod; do
  if [ ! -f "$f" ]; then
    echo -e "${RED}❌ Required env file missing: $f${NC}"; exit 1; fi
done

if grep -q "django-insecure-CHANGE-THIS-IN-PRODUCTION" .env.prod; then
  echo -e "${RED}⚠️  WARNING: Default SECRET_KEY in .env.prod${NC}";
fi

COMPOSE_FILE=Docker/compose.prod.yml
echo -e "${BLUE}🔧 Using compose file: ${COMPOSE_FILE}${NC}"
docker compose -f ${COMPOSE_FILE} up --build -d

echo -e "${YELLOW}⏳ Waiting for services...${NC}"; sleep 8
if docker compose -f ${COMPOSE_FILE} ps | grep -q Up; then
  echo -e "${GREEN}✅ Production stack up${NC}"; else echo -e "${RED}⚠️  Some services not running${NC}"; fi

echo -e "${GREEN}🌐 Production URLs:${NC}"
echo "  App: http://localhost:8000" 
echo ""
echo -e "${YELLOW}� Useful commands:${NC}"
echo "  Logs: docker compose -f ${COMPOSE_FILE} logs -f"
echo "  App logs: docker compose -f ${COMPOSE_FILE} logs app"
echo "  Worker logs: docker compose -f ${COMPOSE_FILE} logs worker"
echo "  Exec shell: docker compose -f ${COMPOSE_FILE} exec app bash"
echo "  Migrations (re-run): docker compose -f ${COMPOSE_FILE} exec app uv run python manage.py migrate"
echo "  Create superuser: docker compose -f ${COMPOSE_FILE} exec app uv run python manage.py createsuperuser"
echo ""
echo -e "${BLUE}🛑 To stop: docker compose -f ${COMPOSE_FILE} down${NC}"
