# Use official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

# Set work directory
WORKDIR /app

# Install dependencies
COPY backend/requirements.txt /app/backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy project
COPY backend/ /app/backend/

# Run the application (Render binds to $PORT dynamically)
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --forwarded-allow-ips "*"
