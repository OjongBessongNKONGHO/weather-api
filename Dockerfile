# Python 3.11 slim — smaller image than the full Python image.
# Slim omits development tools and documentation that a running
# API container never needs, reducing the image size significantly.
FROM python:3.11-slim

# Set working directory inside the container.
WORKDIR /app

# Copy requirements first — before the application code.
# Docker builds images in layers. If requirements.txt hasn't changed,
# Docker reuses the cached layer and skips pip install entirely.
# This makes rebuilds after code changes much faster.
COPY requirements.txt .

# Install dependencies.
# --no-cache-dir prevents pip from storing the download cache inside
# the image — keeps the image smaller.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code.
COPY . .

# Document which port the app listens on.
# This doesn't actually publish the port — docker-compose does that.
EXPOSE 8000

# Start the API with uvicorn.
# --host 0.0.0.0 makes it reachable from outside the container.
# No --reload in production — that's only for development.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]