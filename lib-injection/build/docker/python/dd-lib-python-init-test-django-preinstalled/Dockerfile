FROM public.ecr.aws/docker/library/python:3.9

ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE django_app
WORKDIR /src
ADD . /src

# Install ddtrace beforehand to ensure it doesn't get overridden.
RUN pip install django ddtrace==1.12.0
EXPOSE 18080

# Many users run a non-root user, ensure this is supported by the injection mechanism
USER 1000
CMD ddtrace-run python -m django runserver 0.0.0.0:18080
