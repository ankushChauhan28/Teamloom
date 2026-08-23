# ==============================================================================
# STAGE 1: Builder Stage (Dependency Compilation & Installation)
# ==============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies required for compiling C-extensions (e.g. psycopg2/bcrypt)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Layer Caching Optimization: Copy requirements.txt first
COPY requirements.txt .

# Install production dependencies (including sub-dependencies like email-validator) into /install
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# ==============================================================================
# STAGE 2: Production Runtime Stage (Slim & Non-Root)
# ==============================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:$PATH"

WORKDIR /app

# Install runtime PostgreSQL client library
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy installed dependencies and binaries directly from builder stage
COPY --from=builder /install /usr/local

# Security Best Practice: Create an unprivileged non-root user & group
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup --home /home/appuser appuser

# Copy application source files
COPY app/ /app/app/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/
COPY scripts/ /app/scripts/
COPY docker-entrypoint.sh /app/

# Set executable permissions on entrypoint script and grant ownership to appuser
RUN chmod +x /app/docker-entrypoint.sh && \
    chown -R appuser:appgroup /app /home/appuser

# Switch execution context to non-root user
USER appuser

EXPOSE 8000

# Entrypoint script executes database migrations prior to launching Uvicorn
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default server command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
