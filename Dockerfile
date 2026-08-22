FROM python:3.12-slim

WORKDIR /app

# Dependências de sistema para o Chromium do Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg ca-certificates \
    fonts-liberation fonts-unifont \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    libgtk-3-0 libx11-6 libx11-xcb1 libxcb1 \
    libxext6 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

COPY requeriments.txt .
RUN pip install --no-cache-dir -r requeriments.txt

# Instala o browser do Playwright
RUN playwright install chromium
# (opcional, se faltar lib no slim)
# RUN playwright install-deps chromium

COPY main.py .
COPY .env.example .env.example

# (opcional) se for usar NopeCHA no container
# COPY nopecha-extension/ ./nopecha-extension/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
