# =============================================================================
# Stage 1: Build React PWA Frontend
# =============================================================================
FROM node:20-slim AS builder

WORKDIR "/app/frontend/Mejorar flujo de suscripciones"

# Install pnpm and dependencies
RUN npm install -g pnpm@latest
COPY ["frontend/Mejorar flujo de suscripciones/package.json", "frontend/Mejorar flujo de suscripciones/pnpm-lock.yaml*", "./"]
RUN pnpm install

# Copy application source and build production bundle
COPY ["frontend/Mejorar flujo de suscripciones/", "./"]
RUN pnpm run build

# =============================================================================
# Stage 2: Python FastAPI Runtime
# =============================================================================
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    FRONTEND_DIST=/app/frontend/dist

# Install backend dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY backend/ /app/backend/

# Copy built frontend assets from builder stage
COPY --from=builder ["/app/frontend/Mejorar flujo de suscripciones/dist", "/app/frontend/dist"]
COPY --from=builder ["/app/frontend/Mejorar flujo de suscripciones/dist", "/app/frontend/Mejorar flujo de suscripciones/dist"]

# Create non-root user and set permissions
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
