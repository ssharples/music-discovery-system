# Backend Dockerfile - Production ready with Playwright support
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install system dependencies for Playwright and Crawl4AI
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
        # Playwright system dependencies
        libnss3 \
        libnspr4 \
        libatk-bridge2.0-0 \
        libdrm2 \
        libxkbcommon0 \
        libgtk-3-0 \
        libgbm1 \
        libasound2 \
        # Additional dependencies for Chromium
        fonts-liberation \
        libappindicator3-1 \
        libasound2 \
        libatk-bridge2.0-0 \
        libatspi2.0-0 \
        libdrm2 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        xdg-utils \
        # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements-minimal.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && echo "📦 Installing requirements..." \
    && pip install --no-cache-dir -r requirements-minimal.txt \
    && echo "🔍 Verifying installations..." \
    && pip list | grep -E "(firecrawl|playwright|crawl4ai)" \
    && echo "🎭 Installing Playwright browsers..." \
    && playwright install chromium \
    && playwright install-deps chromium \
    && echo "🐍 Testing critical imports..." \
    && python -c "import crawl4ai; print('✅ Crawl4AI imported successfully')" \
    && python -c "from playwright.async_api import async_playwright; print('✅ Playwright imported successfully')" \
    && echo "✅ All dependencies and browsers installed successfully"

# Copy application code
COPY ./app /app/app

# Create non-root user and set permissions
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app \
    && mkdir -p /ms-playwright \
    && chown -R appuser:appuser /ms-playwright

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 