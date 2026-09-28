FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app
RUN python /app/reconstruct_model.py --output /app/modele_matching_adresses_v3.joblib
COPY scripts /app/scripts
RUN mkdir -p /data/ban && useradd -m -u 10001 appuser && chown -R appuser:appuser /app /data
USER appuser

ENV MODEL_PATH=/app/modele_matching_adresses_v3.joblib \
    BAN_DB_PATH=/data/ban/ban.sqlite \
    API_URL=http://api:8000

EXPOSE 8000 8501
