FROM python:3.9-slim

# Устанавливаем зависимости
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    # Добавляем v4l-utils для диагностики камеры внутри контейнера
    v4l-utils \ 
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p snapshots

# PYTHONUNBUFFERED=1 позволяет видеть логи в реальном времени
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["python", "-m", "src.main"]