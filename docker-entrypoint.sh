#!/bin/sh
set -e

echo "========================================================"
echo " Starting Container Startup Routine"
echo "========================================================"

# Step 1: Execute database migrations automatically before app starts
echo "[+] Running database schema migrations (alembic upgrade head)..."
alembic upgrade head
echo "[+] Database schema migrations completed successfully!"

echo "========================================================"
echo " Launching FastAPI Application Server"
echo "========================================================"

# Step 2: Hand over execution control to the main command (CMD in Dockerfile)
exec "$@"
