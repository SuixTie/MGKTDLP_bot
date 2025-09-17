FROM python:3.9-slim

# Установка antiword и libreoffice
RUN apt-get update && \
    apt-get install -y antiword libreoffice && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Проверка установки antiword и libreoffice
RUN which antiword || { echo "antiword installation failed"; exit 1; }
RUN libreoffice --version || { echo "libreoffice installation failed"; exit 1; }

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . /app
WORKDIR /app

# Команда для запуска
CMD ["python", "main.py"]
