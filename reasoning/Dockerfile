FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p reasoning && touch reasoning/__init__.py
COPY app/ ./reasoning/app/
COPY tests/ ./reasoning/tests/
COPY pytest.ini ./reasoning/
HEALTHCHECK --interval=15s --timeout=5s --retries=3 --start-period=60s \
    CMD curl -sf http://localhost:8000/health || exit 1
CMD ["uvicorn", "reasoning.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
