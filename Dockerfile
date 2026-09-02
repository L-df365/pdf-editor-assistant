FROM python:3.10-slim

# Install LibreOffice, tkinter and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-core \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    python3-tk \
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    x11-apps \
    && rm -rf /var/lib/apt/lists/*

# Set Chinese fonts and display
ENV LANG=C.UTF-8
ENV DISPLAY=:0

WORKDIR /app

# Copy application
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make scripts executable
RUN chmod +x main.py setup.sh

ENTRYPOINT ["python"]
CMD ["main.py"]
