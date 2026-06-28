FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Some dependencies may require build tools for native extensions.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy only what we need for dependency installation first (better layer caching).
COPY pyproject.toml README.md ./
COPY config.yaml ./
COPY src ./src

# Runtime output dirs (also safe when mounting volumes).
RUN mkdir -p templates reports logs

RUN python -c "import tomllib, pathlib; d=tomllib.loads(pathlib.Path('pyproject.toml').read_text('utf-8')); print('\\n'.join(d['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt

CMD ["sh", "-c", "uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8000}"]

