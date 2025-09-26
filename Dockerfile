FROM python:3.10-slim

# Install dependency sistem buat build dlib & face_recognition
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements dulu (biar cache build lebih efisien)
COPY requirements.txt .

# Install python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua source code
COPY . .

# Jalankan pakai gunicorn (production server)
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]
