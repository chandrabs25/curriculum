FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

COPY requirements-demo-vector.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-demo-vector.txt

COPY curriculum_engine ./curriculum_engine
COPY data/textbook_sources ./data/textbook_sources
COPY data/relationship_artifacts ./data/relationship_artifacts
COPY data/retrieval_index ./data/retrieval_index

CMD ["sh", "-c", "python -m uvicorn curriculum_engine.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
