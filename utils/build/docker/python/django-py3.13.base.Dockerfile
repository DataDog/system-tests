FROM python:3.13-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl

# print versions
RUN python --version && curl --version
# install python deps
ENV PIP_ROOT_USER_ACTION=ignore
COPY utils/build/docker/python/django/requirements-django-py3.13.txt /tmp/django-requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/django-requirements.txt

# py-spy lets system-tests dump a weblog's thread stacks from outside the
# process when a remote config apply stalls (see utils/_remote_config.py)
RUN pip install --no-cache-dir py-spy==0.4.2

# docker build --progress=plain -f utils/build/docker/python/django-py3.13.base.Dockerfile -t datadog/system-tests:django-py3.13.base-v12 .
# docker push datadog/system-tests:django-py3.13.base-v12
