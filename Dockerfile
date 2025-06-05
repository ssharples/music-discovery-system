# Multi-stage Dockerfile for Coolify deployment
# Build frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /app

# Copy pre-built frontend
COPY frontend/dist ./frontend/dist

# Build backend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nginx \
    supervisor \
    curl \
    gcc \
    redis-server \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy backend code
COPY backend/app ./app

# Copy frontend build
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html

# Copy configuration files
COPY deployment/nginx.conf /etc/nginx/sites-available/default
COPY deployment/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /usr/share/nginx/html

# Create log directories and set permissions
RUN mkdir -p /var/log/supervisor /var/log/nginx /var/lib/redis && \
    chown -R appuser:appuser /var/log/supervisor /var/log/nginx /var/lib/redis && \
    chmod -R 755 /var/log/supervisor /var/log/nginx

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 80 8000

USER appuser

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"] 