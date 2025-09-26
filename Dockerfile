# Gunakan Python base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install dependencies system (buat face_recognition & cmake dkk)
RUN apt-get update && apt-get install -y \
    build-essential cmake \
    libsm6 libxext6 libxrender-dev \
    libgl1 libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements dan install dependencies Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua file project ke dalam container
COPY . .

# Expose port Flask default
EXPOSE 5000

# Jalankan app.py (tanpa ngrok, cukup Flask di 0.0.0.0)
CMD ["python", "app.py"]
