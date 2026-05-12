FROM public.ecr.aws/docker/library/python:3.11

ENV PYTHONUNBUFFERED 1
ENV DD_INJECT_FORCE 1
ENV DJANGO_SETTINGS_MODULE django_app
WORKDIR /src
ADD . /src
RUN pip install django structlog==16.0.0

EXPOSE 18080
CMD python -m django runserver 0.0.0.0:18080
