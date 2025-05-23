# Use official Python slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy server code and install dependencies
COPY ./ ./observer/
WORKDIR /app/observer
RUN pip install --no-cache-dir -r requirements.txt

# Expose Port
EXPOSE 5001

# Run Observer
CMD ["python", "main.py"]
