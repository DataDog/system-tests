# FROM python:3.9-slim-bullseye
FROM python:3.9

COPY ./requirements.txt  /app/requirements.txt
WORKDIR /app

RUN python -m pip install --upgrade pip
RUN pip install -r requirements.txt

CMD pytest -s

