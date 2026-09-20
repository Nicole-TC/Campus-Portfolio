# --- Imagen base liviana con Python ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema necesarias para compilar psycopg2 (driver de PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalamos primero requirements.txt para aprovechar el cache de Docker:
# si no cambian las dependencias, no las vuelve a instalar en cada build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app

RUN mkdir -p /storage

EXPOSE 8000

# --reload recarga solo al guardar cambios (para desarrollo).
# Para la entrega final del hackathon, sacar --reload.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
