FROM python:3.11-slim

WORKDIR /app

# tesseract-ocr: required for image text extraction (pytesseract wraps this
# binary - it is not installed by the pip package alone).
# build-essential/curl: needed for psycopg and bcrypt wheel builds, and the
# healthcheck below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY app ./app

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
