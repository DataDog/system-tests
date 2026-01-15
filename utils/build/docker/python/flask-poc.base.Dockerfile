FROM python:3.11-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl gcc

# print versions
RUN python --version && curl --version

#DRIVER MSSQL
RUN apt-get update \
    && apt-get install -y curl apt-transport-https gnupg2\
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor | tee /etc/apt/trusted.gpg.d/microsoft.gpg > /dev/null \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev

# this is necessary for the mysqlclient install
RUN apt update && apt install -y pkg-config default-libmysqlclient-dev pkg-config

# install python deps (flask is pinned below because tracer does not support >=2.3.0)
COPY utils/build/docker/python/flask/requirements-flask-poc.txt /tmp/flask-requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/flask-requirements.txt

# docker build --progress=plain -f utils/build/docker/python/flask-poc.base.Dockerfile -t datadog/system-tests:flask-poc.base-v12 .
# docker push datadog/system-tests:flask-poc.base-v12
