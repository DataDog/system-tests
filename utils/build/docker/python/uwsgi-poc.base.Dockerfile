FROM python:3.11-slim

# install bin dependancies
RUN apt-get update && apt-get install -y gcc curl

# print versions
RUN python --version && curl --version

# this is necessary for the mysqlclient install
RUN apt update && apt install -y pkg-config default-libmysqlclient-dev pkg-config

# install python deps
# Tracer does not support flask 2.3.0 or higher, pin the flask version for now
RUN pip install --upgrade pip
RUN pip install 'flask[async]'==2.2.4 flask-login==0.6.3 uWSGI==2.0.26 gevent==24.2.1 requests==2.32.3 pycryptodome==3.20.0 psycopg2-binary==2.9.9 confluent-kafka==2.1.1 graphene==3.4.3
RUN pip install 'moto[ec2,s3,all]'==5.0.14 xmltodict==0.14.2
RUN pip install boto3==1.34.141 kombu==5.3.7 mock==5.1.0 asyncpg==0.29.0 aiomysql==0.2.0 mysql-connector-python==9.0.0 mysqlclient==2.2.4 urllib3==1.26.19 PyMySQL==1.1.1

# docker build --progress=plain -f utils/build/docker/python/uwsgi-poc.base.Dockerfile -t datadog/system-tests:uwsgi-poc.base-v8 .
# docker push datadog/system-tests:uwsgi-poc.base-v8

