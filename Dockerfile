FROM python:3.9-slim

# Установка libreoffice и всех необходимых зависимостей
RUN apt-get update && \
    apt-get install -y libreoffice libreoffice-writer libreoffice-java-common libreoffice-base libreoffice-core \
    default-jre fontconfig libx11-6 libxrender1 libfontconfig1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Проверка установки libreoffice
RUN libreoffice --version || { echo "libreoffice installation failed"; exit 1; }

# Проверка доступности /tmp
RUN mkdir -p /tmp && chmod -R 777 /tmp && ls -ld /tmp

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . /app
WORKDIR /app

# Команда для запуска
CMD ["python", "main.py"]
