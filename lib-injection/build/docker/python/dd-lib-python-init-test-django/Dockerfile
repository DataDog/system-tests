FROM public.ecr.aws/docker/library/python:3.11

ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE django_app
WORKDIR /src
ADD . /src
RUN pip install django
EXPOSE 18080

# Many users run a non-root user, ensure this is supported by the injection mechanism
USER 1000
CMD python -m django runserver 0.0.0.0:18080