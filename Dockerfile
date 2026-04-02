FROM python:3.11-slim

WORKDIR /app

# Copiem dependințele
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiem tot codul, inclusiv claude_sonnet_server.py
COPY . .

# Expunem portul
EXPOSE 5000

# Pornim Gunicorn specificând fișierul tău
CMD ["python", "claude_sonnet_server.py"]
