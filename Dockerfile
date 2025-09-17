FROM python:3.9-slim

# Установка libreoffice, default-jre и дополнительных зависимостей
RUN apt-get update && \
    apt-get install -y libreoffice default-jre fontconfig libx11-6 libxrender1 libfontconfig1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Проверка установки libreoffice
RUN libreoffice --version || { echo "libreoffice installation failed"; exit 1; }

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . /app
WORKDIR /app

# Команда для запуска
CMD ["python", "main.py"]
