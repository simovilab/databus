#!/bin/bash
# Script de verificación para Issue #24: Security and Performance Hygiene

echo "======================================"
echo "Verificación de Security & Performance"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Check Django configuration
echo "1. Verificando configuración de Django..."
if docker-compose exec -T web python manage.py check > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Configuración OK"
else
    echo -e "${RED}✗${NC} Error en configuración"
    docker-compose exec -T web python manage.py check
    exit 1
fi

# 2. Check CORS middleware
echo ""
echo "2. Verificando CORS middleware..."
if docker-compose exec -T web python manage.py shell -c "from django.conf import settings; print('corsheaders' in settings.INSTALLED_APPS)" | grep -q "True"; then
    echo -e "${GREEN}✓${NC} CORS instalado"
else
    echo -e "${RED}✗${NC} CORS no encontrado"
fi

# 3. Check cache middleware
echo ""
echo "3. Verificando cache middleware..."
if docker-compose exec -T web python manage.py shell -c "from api.cache_middleware import ConditionalGetMiddleware; print('OK')" | grep -q "OK"; then
    echo -e "${GREEN}✓${NC} Cache middleware disponible"
else
    echo -e "${RED}✗${NC} Cache middleware no encontrado"
fi

# 4. Check pagination classes
echo ""
echo "4. Verificando pagination classes..."
if docker-compose exec -T web python manage.py shell -c "from api.pagination import StandardPageNumberPagination; print('OK')" | grep -q "OK"; then
    echo -e "${GREEN}✓${NC} Pagination classes disponibles"
else
    echo -e "${RED}✗${NC} Pagination classes no encontradas"
fi

# 5. Test API endpoint with headers
echo ""
echo "5. Probando headers de API..."
RESPONSE=$(curl -s -i http://localhost:8000/api/)

if echo "$RESPONSE" | grep -q "X-Content-Type-Options"; then
    echo -e "${GREEN}✓${NC} Security headers presentes"
else
    echo -e "${YELLOW}⚠${NC} Security headers no encontrados (¿servidor corriendo?)"
fi

if echo "$RESPONSE" | grep -q "X-Response-Time"; then
    echo -e "${GREEN}✓${NC} Response timing header presente"
else
    echo -e "${YELLOW}⚠${NC} Response timing header no encontrado"
fi

# 6. Check CORS settings
echo ""
echo "6. Verificando configuración CORS..."
docker-compose exec -T web python manage.py shell << 'EOF'
from django.conf import settings
print(f"CORS_ALLOW_CREDENTIALS: {getattr(settings, 'CORS_ALLOW_CREDENTIALS', 'Not set')}")
print(f"CORS_PREFLIGHT_MAX_AGE: {getattr(settings, 'CORS_PREFLIGHT_MAX_AGE', 'Not set')}")
print(f"CORS_ALLOWED_ORIGINS: {len(getattr(settings, 'CORS_ALLOWED_ORIGINS', []))} origins configured")
EOF

# 7. Check database connection pooling
echo ""
echo "7. Verificando connection pooling..."
docker-compose exec -T web python manage.py shell << 'EOF'
from django.conf import settings
db_config = settings.DATABASES['default']
print(f"CONN_MAX_AGE: {db_config.get('CONN_MAX_AGE', 'Not set')}")
print(f"Connection timeout: {db_config.get('OPTIONS', {}).get('connect_timeout', 'Not set')}")
EOF

# 8. Test pagination
echo ""
echo "8. Probando pagination..."
PAGINATION_TEST=$(curl -s "http://localhost:8000/api/gtfs/agencies/" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"page_size: {data.get('page_size', 'N/A')}\")" 2>/dev/null)

if [ ! -z "$PAGINATION_TEST" ]; then
    echo -e "${GREEN}✓${NC} Pagination funcionando: $PAGINATION_TEST"
else
    echo -e "${YELLOW}⚠${NC} No se pudo probar pagination (datos no disponibles)"
fi

echo ""
echo "======================================"
echo "Verificación completada"
echo "======================================"
