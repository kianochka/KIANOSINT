FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libffi-dev libxml2-dev libxslt1-dev libpq-dev && pip install -r requirements.txt && apt-get purge -y build-essential && rm -rf /var/lib/apt/lists/*

COPY . .
CMD ["python", "-m", "bot"]