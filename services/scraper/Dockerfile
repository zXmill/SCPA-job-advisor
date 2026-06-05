FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY services/scraper/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/__init__.py ./services/__init__.py
COPY services/shared ./services/shared
COPY services/scraper ./services/scraper
COPY data/skills ./data/skills

EXPOSE 8001
CMD ["uvicorn", "services.scraper.main:app", "--host", "0.0.0.0", "--port", "8001"]
