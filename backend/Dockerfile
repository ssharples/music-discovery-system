# Backend Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && echo "📦 Installing requirements..." \
    && pip install --no-cache-dir -r requirements.txt \
    && echo "🔍 Verifying firecrawl installation..." \
    && echo "📋 Checking pip list for firecrawl..." \
    && pip list | grep -i firecrawl \
    && echo "🔍 Attempting manual firecrawl-py install..." \
    && pip install --no-cache-dir firecrawl-py==1.5.0 --force-reinstall \
    && echo "📋 Checking pip list again..." \
    && pip list | grep -i firecrawl \
    && echo "🐍 Testing Python import..." \
    && python -c "import firecrawl; print('✅ Firecrawl imported successfully'); print(f'Firecrawl version: {firecrawl.__version__ if hasattr(firecrawl, \"__version__\") else \"unknown\"}')" \
    && echo "✅ All dependencies installed successfully"

# Copy application code
COPY ./app /app/app

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 