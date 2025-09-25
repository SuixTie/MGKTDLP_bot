FROM python:3.9-slim

RUN apt-get update && \
    apt-get install -y libreoffice libreoffice-writer libreoffice-java-common libreoffice-base libreoffice-core \
    libreoffice-common fontconfig libx11-6 libxrender1 libfontconfig1 libxinerama1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN libreoffice --version || { echo "libreoffice installation failed"; exit 1; }

ENV HOME=/tmp
RUN mkdir -p /tmp && chmod -R 777 /tmp && ls -ld /tmp

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
WORKDIR /app

CMD ["python", "main.py"]
