#!/bin/bash
# SCPA Secret Generator
# Run: bash scripts/generate_secrets.sh > .env
# WARNING: This will overwrite your existing .env file!

set -euo pipefail

echo "# ============================================================"
echo "# SCPA Platform — Environment Configuration"
echo "# Generated: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "# ============================================================"
echo ""

# Generate cryptographically strong secrets
POSTGRES_USER="scpa_user"
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '\n' | head -c 48)
POSTGRES_DB="scpa_db"
REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d '\n' | head -c 48)
SECRET_KEY=$(openssl rand -base64 64 | tr -d '\n')
JWT_SECRET=$(openssl rand -base64 64 | tr -d '\n')
JWT_REFRESH_SECRET=$(openssl rand -base64 64 | tr -d '\n')

# Application
echo "APP_ENV=development"
echo "LOG_LEVEL=INFO"
echo ""

# Database
echo "# ── Database (PostgreSQL) ──"
echo "POSTGRES_USER=${POSTGRES_USER}"
echo "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}"
echo "POSTGRES_DB=${POSTGRES_DB}"
echo "DATABASE_URL=postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}"
echo ""

# Redis
echo "# ── Redis ──"
echo "REDIS_PASSWORD=${REDIS_PASSWORD}"
echo "REDIS_URL=redis://default:${REDIS_PASSWORD}@localhost:6379/0"
echo ""

# Authentication
echo "# ── Authentication ──"
echo "SECRET_KEY=${SECRET_KEY}"
echo "JWT_SECRET=${JWT_SECRET}"
echo "JWT_ALGORITHM=HS256"
echo "JWT_EXPIRY_HOURS=24"
echo "JWT_REFRESH_SECRET=${JWT_REFRESH_SECRET}"
echo "JWT_REFRESH_EXPIRY_DAYS=30"
echo ""

# ML Services
echo "# ── ML Services (Internal) ──"
echo "NCF_SERVICE_URL=http://ncf-service:8001"
echo "SBERT_SERVICE_URL=http://sbert-service:8002"
echo "DQN_SERVICE_URL=http://dqn-service:8003"
echo "HYBRID_SERVICE_URL=http://hybrid-service:8004"
echo ""

# Frontend
echo "# ── Frontend ──"
echo "NEXT_PUBLIC_API_URL=http://localhost:8000"
echo ""

# Pipeline
echo "# ── Pipeline ──"
echo "SCRAPING_ENABLED=true"
echo "SCRAPING_INTERVAL_HOURS=24"
echo "JOBS_TARGET=5000"
echo ""

# Security
echo "# ── Security ──"
echo "CORS_ORIGINS=http://localhost:3000"
echo "ALLOWED_HOSTS=localhost,127.0.0.1"
echo "RATE_LIMIT_PER_MINUTE=60"
echo ""

# Observability
echo "# ── Observability ──"
echo "SENTRY_DSN="
echo "OTEL_EXPORTER_ENDPOINT=http://localhost:4317"
echo ""

# Email
echo "# ── Email (Future) ──"
echo "SMTP_HOST="
echo "SMTP_PORT=587"
echo "SMTP_USER="
echo "SMTP_PASSWORD="
echo ""

# Warnings
echo "# ============================================================"
echo "# ⚠️  SECRET ROTATION REQUIRED EVERY 90 DAYS"
echo "# ⚠️  NEVER commit this file to version control"
echo "# ⚠️  Store in a secret manager for production"
echo "# ============================================================"