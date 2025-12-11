FROM public.ecr.aws/docker/library/python:3.9

ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE django_app
WORKDIR /src
ADD . /src

RUN pip install django protobuf==3.17.0

# Many users run a non-root user, ensure this is supported by the injection mechanism
USER 1000
CMD ["python","-m","django","runserver","0.0.0.0:18080"]
