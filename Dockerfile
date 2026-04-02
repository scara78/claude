FROM python:3.11-slim

WORKDIR /app

# Copiem fișierul de dependențe
COPY requirements.txt .

# Instalăm bibliotecile
RUN pip install --no-cache-dir -r requirements.txt

# Copiem restul codului (app.py)
COPY . .

# Expunem portul Flask
EXPOSE 5000

# Pornim serverul cu Gunicorn
# "app:app" înseamnă: fișierul app.py, variabila app = Flask(__name__)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app", "--timeout", "120", "--workers", "2"]
