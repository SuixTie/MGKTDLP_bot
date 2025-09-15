FROM python:3.9-slim

# Устанавливаем зависимости системы
RUN apt-get update && apt-get install -y antiword && apt-get clean

# Копируем проект
WORKDIR /app
COPY . .

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Указываем команду для запуска
CMD ["python", "main.py"]
