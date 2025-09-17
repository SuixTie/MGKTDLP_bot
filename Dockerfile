FROM python:3.9-slim

# Установка antiword и других зависимостей
RUN apt-get update && \
    apt-get install -y antiword && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Проверка установки antiword
RUN antiword -v || { echo "antiword installation failed"; exit 1; }

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . /app
WORKDIR /app

# Команда для запуска
CMD ["python", "main.py"]
