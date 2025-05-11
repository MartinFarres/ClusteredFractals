# Use official Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy puller source code
COPY ./main.py /app

# Install dependencies
RUN pip install --no-cache-dir redis kubernetes

# Entry point for the puller
CMD ["python", "main.py"]
