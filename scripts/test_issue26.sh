#!/bin/bash

# Test script for Issue #26 - Unit and Integration Tests
# Run tests and validate testing infrastructure

set -e

echo "================================================"
echo "Testing Infrastructure Validation"
echo "================================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function for tests
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -n "Test: $test_name ... "
    
    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

echo "Phase 1: File Existence Checks"
echo "-------------------------------"

run_test "pytest.ini exists" "test -f pytest.ini"
run_test "conftest.py exists" "test -f tests/conftest.py"
run_test "test_serializers.py exists" "test -f tests/test_serializers.py"
run_test "test_api_endpoints.py exists" "test -f tests/test_api_endpoints.py"
run_test "test_gtfs_endpoints.py exists" "test -f tests/test_gtfs_endpoints.py"
run_test "test_contract.py exists" "test -f tests/test_contract.py"
run_test "CI workflow exists" "test -f .github/workflows/ci.yml"
run_test "Testing documentation exists" "test -f docs/testing.md"
run_test "requirements-dev.txt exists" "test -f requirements-dev.txt"

echo ""
echo "Phase 2: Configuration Validation"
echo "----------------------------------"

run_test "pytest.ini has DJANGO_SETTINGS_MODULE" "grep -q 'DJANGO_SETTINGS_MODULE' pytest.ini"
run_test "pytest.ini has test discovery patterns" "grep -q 'python_files' pytest.ini"
run_test "pytest.ini has coverage config" "grep -q 'addopts.*--cov' pytest.ini"
run_test "pytest.ini has custom markers" "grep -q 'markers' pytest.ini"
run_test "pyproject.toml has coverage config" "grep -q 'tool.coverage' pyproject.toml"

echo ""
echo "Phase 3: Test File Validation"
echo "------------------------------"

run_test "conftest.py has fixtures" "grep -q '@pytest.fixture' tests/conftest.py"
run_test "conftest.py has factories" "grep -q 'Factory' tests/conftest.py"
run_test "test_serializers.py has unit tests" "grep -q '@pytest.mark.unit' tests/test_serializers.py"
run_test "test_api_endpoints.py has integration tests" "grep -q '@pytest.mark.integration' tests/test_api_endpoints.py"
run_test "test_contract.py has contract tests" "grep -q '@pytest.mark.contract' tests/test_contract.py"

echo ""
echo "Phase 4: CI/CD Workflow Validation"
echo "-----------------------------------"

run_test "CI workflow has lint job" "grep -q 'name: Code Quality' .github/workflows/ci.yml"
run_test "CI workflow has test job" "grep -q 'name: Run Tests' .github/workflows/ci.yml"
run_test "CI workflow has build job" "grep -q 'name: Build Docker' .github/workflows/ci.yml"
run_test "CI workflow has security job" "grep -q 'name: Security Scan' .github/workflows/ci.yml"
run_test "CI workflow uses PostgreSQL" "grep -q 'postgis/postgis' .github/workflows/ci.yml"
run_test "CI workflow uses Redis" "grep -q 'redis:' .github/workflows/ci.yml"

echo ""
echo "Phase 5: Dependencies Check"
echo "---------------------------"

run_test "pytest in requirements-dev.txt" "grep -q 'pytest' requirements-dev.txt"
run_test "pytest-django in requirements-dev.txt" "grep -q 'pytest-django' requirements-dev.txt"
run_test "pytest-cov in requirements-dev.txt" "grep -q 'pytest-cov' requirements-dev.txt"
run_test "factory-boy in requirements-dev.txt" "grep -q 'factory-boy' requirements-dev.txt"
run_test "faker in requirements-dev.txt" "grep -q 'faker' requirements-dev.txt"
run_test "black in requirements-dev.txt" "grep -q 'black' requirements-dev.txt"
run_test "isort in requirements-dev.txt" "grep -q 'isort' requirements-dev.txt"
run_test "flake8 in requirements-dev.txt" "grep -q 'flake8' requirements-dev.txt"

echo ""
echo "Phase 6: Test Structure Validation"
echo "-----------------------------------"

# Count test classes
TEST_CLASSES=$(grep -r "^class Test" tests/*.py | wc -l)
run_test "At least 10 test classes" "test $TEST_CLASSES -ge 10"

# Count test methods
TEST_METHODS=$(grep -r "def test_" tests/*.py | wc -l)
run_test "At least 30 test methods" "test $TEST_METHODS -ge 30"

# Check test markers
run_test "Unit test markers present" "grep -q '@pytest.mark.unit' tests/*.py"
run_test "Integration test markers present" "grep -q '@pytest.mark.integration' tests/*.py"
run_test "Contract test markers present" "grep -q '@pytest.mark.contract' tests/*.py"

echo ""
echo "Phase 7: Documentation Validation"
echo "----------------------------------"

run_test "Testing docs exist" "test -f docs/testing.md"
run_test "Testing docs mention pytest" "grep -q 'pytest' docs/testing.md"
run_test "Testing docs mention coverage" "grep -q 'coverage' docs/testing.md"
run_test "Testing docs mention fixtures" "grep -q 'fixtures' docs/testing.md"
run_test "Testing docs have examples" "grep -q '```python' docs/testing.md"

echo ""
echo "================================================"
echo "Summary"
echo "================================================"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All validation tests passed!${NC}"
    echo ""
    echo "Testing infrastructure is ready. Next steps:"
    echo "1. Install dependencies: pip install -r requirements-dev.txt"
    echo "2. Run tests: pytest tests/ -v"
    echo "3. Check coverage: pytest tests/ --cov=api --cov=feed --cov=gtfs --cov-report=html"
    echo "4. View coverage report: open htmlcov/index.html"
    exit 0
else
    echo -e "${RED}✗ Some validation tests failed${NC}"
    exit 1
fi
