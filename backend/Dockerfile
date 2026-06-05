FROM python:3.11-slim

# System deps for OpenCV, Playwright, Pillow
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgl1-mesa-glx \
    curl wget git build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (for generic scraper)
RUN playwright install chromium --with-deps

COPY . .

EXPOSE 8000
