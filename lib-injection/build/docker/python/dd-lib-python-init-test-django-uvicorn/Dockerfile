FROM public.ecr.aws/docker/library/python:3.12

ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE django_app
WORKDIR /src
ADD . /src
RUN pip install django==5.2.12 uvicorn==0.44.0
EXPOSE 18080
CMD uvicorn --host 0.0.0.0 --port 18080 django_app:application
