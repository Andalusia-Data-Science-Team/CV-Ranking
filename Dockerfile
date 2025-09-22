# Base image
FROM python:3.10-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies (for pandas, openpyxl, PyPDF2, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic1 \
    poppler-utils

# Copy requirements file if you have one
# Otherwise install packages directly
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY src/ src/
COPY app.py .

# Expose Streamlit default port
EXPOSE 8501

# Streamlit entrypoint
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
