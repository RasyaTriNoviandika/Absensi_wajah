FROM python:3.11-slim

# Install system dependencies for dlib and face_recognition
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libgl1 \
    libglib2.0-0 \
    libboost-all-dev \
    libopenblas-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Upgrade pip (biar build wheel lancar)
RUN pip install --upgrade pip

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Jalankan app dengan gunicorn
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:8000"]
