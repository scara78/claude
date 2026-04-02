# Dockerfile final corectat
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000

# Folosim gthread pentru a permite operațiuni I/O lungi (cererea către Claude)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "claude_sonnet_server:app", "--workers", "1", "--threads", "4", "--timeout", "120"]
