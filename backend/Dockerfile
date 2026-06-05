FROM python:3.11-slim

# libgl1-mesa-glx was renamed to libgl1 in Debian Trixie
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libsm6 libxext6 libxrender-dev \
    libgl1 \
    curl wget git build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium --with-deps 2>/dev/null || true

COPY . .

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
