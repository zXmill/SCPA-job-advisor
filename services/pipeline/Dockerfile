FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY services/pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/__init__.py ./services/__init__.py
COPY services/pipeline ./services/pipeline

EXPOSE 8005

CMD ["uvicorn", "services.pipeline.main:api", "--host", "0.0.0.0", "--port", "8005"]
