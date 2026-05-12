FROM python:3.12-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl

# print versions
RUN python --version && curl --version

# install python deps
ENV PIP_ROOT_USER_ACTION=ignore
COPY utils/build/docker/python/django/requirements-python3.12.txt /tmp/django-requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/django-requirements.txt


# docker build --progress=plain -f utils/build/docker/python/python3.12.base.Dockerfile -t datadog/system-tests:python3.12.base-v13 .
# docker push datadog/system-tests:python3.12.base-v13
