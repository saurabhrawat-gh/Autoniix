ARG PYTHON_IMAGE=python:3.12.7-slim
FROM ${PYTHON_IMAGE}

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 120 -r requirements.txt

RUN python -m spacy download en_core_web_sm \
    && python -c "import nltk; nltk.download('wordnet', quiet=True); nltk.download('omw-1.4', quiet=True)"

COPY shared/python/ ./src/
COPY backend/api/core/ ./src/services_api/
COPY backend/workers/temporal/workers/ ./src/temporal_workers/
COPY scripts/ ./scripts/

ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["python", "-m", "services_api.research.main"]
