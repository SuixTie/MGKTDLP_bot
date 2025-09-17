FROM python:3.9-slim

# Установка antiword
RUN apt-get update && \
    apt-get install -y antiword && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Проверка установки antiword
RUN which antiword || { echo "antiword installation failed"; exit 1; }

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . /app
WORKDIR /app

# Команда для запуска
CMD ["python", "main.py"]
