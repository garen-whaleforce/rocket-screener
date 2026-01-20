# Rocket Screener - Daily Newsletter Pipeline
# v10 Deployment Configuration

FROM python:3.11-slim

WORKDIR /app

# System dependencies for matplotlib fonts, cron, and SSL
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    fonts-dejavu-core \
    cron \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY .env.example ./.env.example

# Create output directory
RUN mkdir -p /app/output

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Default command runs the daily pipeline
CMD ["python", "-m", "app.run"]
