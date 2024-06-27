FROM python:3.12-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl git gcc g++ make cmake

# print versions
RUN python --version && curl --version

# install python deps
# Tracer does not support flask 2.3.0 or higher, pin the flask version for now
RUN pip install 'flask[async]'==2.2.4 flask-login uwsgi gevent requests pycryptodome psycopg2-binary confluent-kafka==2.1.1

# this is necessary for the mysqlclient install
RUN apt update && apt install -y pkg-config default-libmysqlclient-dev pkg-config

RUN pip install boto3 kombu mock asyncpg aiomysql mysql-connector-python pymysql mysqlclient urllib3

# docker build --progress=plain -f utils/build/docker/python/uwsgi-poc.base.Dockerfile -t datadog/system-tests:uwsgi-poc.base-v2 .
# docker push datadog/system-tests:uwsgi-poc.base-v2

