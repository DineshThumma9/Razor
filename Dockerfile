FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (Redis removed, Railway will handle it)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy project configuration
COPY backend/pyproject.toml backend/uv.lock* ./backend/

# Install dependencies using uv
RUN cd backend && uv sync --frozen --no-cache

# Copy the rest of the application
COPY backend ./backend
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

ENV PYTHONPATH=/app/backend/src

EXPOSE 8000

# Start Supervisor to run both Uvicorn and Taskiq in one container
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
