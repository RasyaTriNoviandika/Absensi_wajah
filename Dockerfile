# Gunakan image yang sudah ada dlib & face_recognition
FROM python:3.9

# Install dependencies sistem dasar
RUN apt-get update && apt-get install -y \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua kode
COPY . .

# Jalankan Flask
CMD ["python", "app.py"]
