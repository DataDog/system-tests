FROM python:3.13-alpine

WORKDIR /app

RUN apk add --no-cache curl

COPY ./utils/build/docker/lambda_proxy/pyproject.toml ./
RUN pip install --no-cache-dir .

COPY utils/build/docker/lambda_proxy/main.py ./

ENTRYPOINT ["gunicorn", "--bind=0.0.0.0:7777", "--workers=1", "main:app"]
