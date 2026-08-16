FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg ca-certificates fonts-liberation \
    libnss3 libatk-bridge2.0-0 libgtk-3-0 libasound2 libgbm1 \
    && rm -rf /var/lib/apt/lists/*

COPY requeriments.txt .
RUN pip install --no-cache-dir -r requeriments.txt

RUN scrapling install

COPY main.py .

EXPOSE 8000

# Health check para monitoramento automático
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]