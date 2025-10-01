# Base image
FROM python:3.10-slim

# Set working directory inside container
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY app.py .

# Expose Dash port
EXPOSE 8050

# Command to run Dash
CMD ["python", "app.py"]
