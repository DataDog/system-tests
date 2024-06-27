FROM python:3.11

COPY ./requirements.txt /app/requirements.txt
WORKDIR /app

RUN pip install -r requirements.txt
RUN pip install json-schema-for-humans==0.33.2
RUN pip install gunicorn

COPY . /app

EXPOSE 80
CMD PYTHONPATH=. exec gunicorn -w 4 -b 0.0.0.0:80 utils.interfaces.schemas.serve_doc:app
