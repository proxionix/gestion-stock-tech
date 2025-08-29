# Multi-stage build for production-ready Django app
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND noninteractive

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        gettext \
        gcc \
        g++ \
        libc6-dev \
        libpq-dev \
        curl \
        netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN groupadd -r app && useradd -r -g app app

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create necessary directories
RUN mkdir -p staticfiles media logs \
    && chown -R app:app /app \
    && chmod +x scripts/*.sh 2>/dev/null || true

# Compile translations
RUN python manage.py compilemessages

# Collect static files
RUN python manage.py collectstatic --noinput

# Change to app user
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--worker-class", "sync", "--timeout", "120", "--keep-alive", "2", "--max-requests", "1000", "--max-requests-jitter", "100", "config.wsgi:application"]

# Development stage
FROM base as development

USER root

# Install development dependencies
RUN pip install --no-cache-dir \
    django-extensions \
    django-debug-toolbar \
    ipython

USER app

# Override command for development
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Production stage
FROM base as production

# Install production WSGI server
USER root
RUN pip install --no-cache-dir gunicorn

USER app

# Production command (already set in base)
