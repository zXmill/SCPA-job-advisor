#!/bin/bash
# SCPA Environment Validation Script
# Run: bash scripts/validate_env.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================="
echo " SCPA Environment Validation"
echo "============================================="

ERRORS=0

check() {
    local name="$1"
    local value="$2"
    if [ -z "$value" ]; then
        echo -e "${RED}✗ $name: NOT SET${NC}"
        ((ERRORS++))
    else
        echo -e "${GREEN}✓ $name: set${NC}"
    fi
}

# Check .env file
if [ -f .env ]; then
    echo -e "${GREEN}✓ .env file found${NC}"
    source .env
else
    echo -e "${YELLOW}⚠ .env file not found — using defaults from docker-compose.yml${NC}"
fi

# Check required variables
echo ""
echo "── Required Environment Variables ──"
check "POSTGRES_PASSWORD" "${POSTGRES_PASSWORD:-}"
check "REDIS_PASSWORD" "${REDIS_PASSWORD:-}"
check "DATABASE_URL" "${DATABASE_URL:-}"
check "REDIS_URL" "${REDIS_URL:-}"
check "SECRET_KEY" "${SECRET_KEY:-}"
check "JWT_SECRET" "${JWT_SECRET:-}"

# Check Docker is running
echo ""
echo "── Docker Status ──"
if docker info > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Docker is running${NC}"
else
    echo -e "${RED}✗ Docker is not running${NC}"
    ((ERRORS++))
fi

# Check docker-compose
if docker compose version > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Docker Compose is available${NC}"
else
    echo -e "${RED}✗ Docker Compose not available${NC}"
    ((ERRORS++))
fi

# Check ports
echo ""
echo "── Port Conflicts ──"
for port in 5432 6379 3000 8000 8001 8002 8003 8004; do
    if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
        echo -e "${YELLOW}⚠ Port $port is in use${NC}"
    else
        echo -e "${GREEN}✓ Port $port is available${NC}"
    fi
done

# Check secrets directory
echo ""
echo "── Secrets Management ──"
if [ -d "secrets" ]; then
    for f in pg_user.txt pg_password.txt pg_db.txt redis_password.txt; do
        if [ -f "secrets/$f" ]; then
            echo -e "${GREEN}✓ secrets/$f exists${NC}"
        else
            echo -e "${RED}✗ secrets/$f MISSING${NC}"
            ((ERRORS++))
        fi
    done
else
    echo -e "${YELLOW}⚠ secrets/ directory not found${NC}"
fi

# Summary
echo ""
echo "============================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ $ERRORS error(s) found${NC}"
    exit 1
fi