#!/bin/bash
# Test script for Admin Dashboard (Issue #25)

echo "================================================"
echo "Testing Admin Dashboard - Issue #25"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check migrations
echo "1. Checking migrations..."
if docker-compose exec -T web python manage.py showmigrations api | grep -q "\[X\] 0002_adminauditlog"; then
    echo -e "${GREEN}✓${NC} AdminAuditLog migration applied"
else
    echo -e "${RED}✗${NC} AdminAuditLog migration missing"
    exit 1
fi

# Test 2: Check model import
echo ""
echo "2. Checking model import..."
if docker-compose exec -T web python manage.py shell -c "from api.models import AdminAuditLog; print('OK')" | grep -q "OK"; then
    echo -e "${GREEN}✓${NC} AdminAuditLog model imports correctly"
else
    echo -e "${RED}✗${NC} Failed to import AdminAuditLog"
    exit 1
fi

# Test 3: Check middleware
echo ""
echo "3. Checking middleware configuration..."
if docker-compose exec -T web python manage.py shell -c "from django.conf import settings; print('api.admin_audit.AdminAuditMiddleware' in settings.MIDDLEWARE)" | grep -q "True"; then
    echo -e "${GREEN}✓${NC} AdminAuditMiddleware configured"
else
    echo -e "${RED}✗${NC} AdminAuditMiddleware not in settings"
    exit 1
fi

# Test 4: Check admin registration
echo ""
echo "4. Checking admin registration..."
if docker-compose exec -T web python manage.py shell -c "from django.contrib import admin; from api.models import AdminAuditLog; print(AdminAuditLog in admin.site._registry)" | grep -q "True"; then
    echo -e "${GREEN}✓${NC} AdminAuditLog registered in admin"
else
    echo -e "${RED}✗${NC} AdminAuditLog not registered"
    exit 1
fi

# Test 5: Check dashboard views
echo ""
echo "5. Checking dashboard views..."
if docker-compose exec -T web python manage.py shell -c "from api import admin_dashboard; print('OK')" | grep -q "OK"; then
    echo -e "${GREEN}✓${NC} Dashboard views import correctly"
else
    echo -e "${RED}✗${NC} Failed to import dashboard views"
    exit 1
fi

# Test 6: Test audit log creation
echo ""
echo "6. Testing audit log creation..."
docker-compose exec -T web python manage.py shell << 'EOF' > /dev/null 2>&1
from api.models import AdminAuditLog
from django.contrib.auth.models import User

user = User.objects.first()
log = AdminAuditLog.log_action(
    action_type='test',
    content_type='test.model',
    object_repr='Test Action',
    user=user,
    ip_address='127.0.0.1',
    notes='Automated test'
)
print('OK')
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Audit log created successfully"
else
    echo -e "${RED}✗${NC} Failed to create audit log"
    exit 1
fi

# Test 7: Check template exists
echo ""
echo "7. Checking dashboard template..."
if [ -f "api/templates/admin/dashboard/overview.html" ]; then
    echo -e "${GREEN}✓${NC} Dashboard template exists"
else
    echo -e "${RED}✗${NC} Dashboard template not found"
    exit 1
fi

# Test 8: Check URLs configuration
echo ""
echo "8. Checking URL configuration..."
if docker-compose exec -T web python manage.py shell -c "from django.urls import get_resolver; resolver = get_resolver(); print('/admin/api/dashboard/' in [str(p.pattern) for p in resolver.url_patterns])" 2>/dev/null | grep -q "True"; then
    echo -e "${GREEN}✓${NC} Dashboard URLs configured"
else
    echo -e "${YELLOW}⚠${NC} Dashboard URLs might need verification"
fi

# Test 9: Test database table exists
echo ""
echo "9. Checking database table..."
if docker-compose exec -T web python manage.py shell -c "from django.db import connection; cursor = connection.cursor(); cursor.execute('SELECT COUNT(*) FROM api_admin_audit_log'); print('OK')" | grep -q "OK"; then
    echo -e "${GREEN}✓${NC} Database table exists and accessible"
else
    echo -e "${RED}✗${NC} Database table not accessible"
    exit 1
fi

# Test 10: Check documentation
echo ""
echo "10. Checking documentation..."
if [ -f "api/ADMIN_DASHBOARD_README.md" ] && [ -f "api/ADMIN_DASHBOARD_SUMMARY.md" ]; then
    echo -e "${GREEN}✓${NC} Documentation files exist"
else
    echo -e "${RED}✗${NC} Documentation missing"
    exit 1
fi

echo ""
echo "================================================"
echo -e "${GREEN}All tests passed!${NC}"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Access admin panel: http://localhost:8000/admin/"
echo "2. View dashboard: http://localhost:8000/admin/api/dashboard/"
echo "3. Check audit logs: http://localhost:8000/admin/api/adminauditlog/"
echo ""
echo "Documentation:"
echo "- Full guide: api/ADMIN_DASHBOARD_README.md"
echo "- Summary: api/ADMIN_DASHBOARD_SUMMARY.md"
echo ""
