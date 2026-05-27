ARG PYTHON_BASE_IMAGE=python:3.11-slim
FROM ${PYTHON_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
ARG PIP_INDEX_URL
ARG PIP_TRUSTED_HOST
RUN pip install --no-cache-dir ${PIP_INDEX_URL:+-i "$PIP_INDEX_URL"} ${PIP_TRUSTED_HOST:+--trusted-host "$PIP_TRUSTED_HOST"} -r requirements.txt

RUN rm -rf /app/app
COPY app ./app

EXPOSE 8000

CMD ["python", "-m", "app.core.main"]
