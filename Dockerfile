FROM python:3.10-slim

# Install LibreOffice and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-core \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/*

# Set Chinese fonts
ENV LANG=C.UTF-8

WORKDIR /app

# Copy application
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make scripts executable
RUN chmod +x main.py setup.sh

ENTRYPOINT ["python", "main.py"]
