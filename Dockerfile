# Use official lightweight Python image
FROM python:3.11-slim

# Set environment variables
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing pyc files to disc
# PYTHONUNBUFFERED: Prevents Python from buffering stdout and stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies required for building python packages (if any)
# libpq-dev is needed for psycopg2/asyncpg compilation sometimes
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
# We copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user for security (SOC 2 Requirement)
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# Expose the port (Documentary only, actual mapping in docker-compose)
EXPOSE 8000

# Define the entrypoint script
CMD ["./entrypoint.sh"]