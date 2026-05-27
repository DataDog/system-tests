FROM public.ecr.aws/docker/library/python:3.10

ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE django_app
WORKDIR /src
ADD . /src
RUN pip install django==5.2.12 gunicorn==25.3.0
EXPOSE 18080
CMD gunicorn --bind :18080 django_app:application
