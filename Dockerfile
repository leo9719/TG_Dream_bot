# Используем официальный Python с ffmpeg
FROM python:3.11-slim

# Устанавливаем ffmpeg и необходимые пакеты
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем файлы проекта
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создаём папку для скачивания
RUN mkdir -p downloads

# Запуск
CMD ["python", "bot.py"]