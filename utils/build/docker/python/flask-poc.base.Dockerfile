FROM python:3.11-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl git gcc g++ make cmake

# print versions
RUN python --version && curl --version

#DRIVER MSSQL
RUN apt-get update \
    && apt-get install -y curl apt-transport-https gnupg2\
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev

# this is necessary for the mysqlclient install
RUN apt update && apt install -y pkg-config default-libmysqlclient-dev pkg-config

#pip install driver pymysql and pyodbc(mssql)
RUN pip install pymysql==1.1.1 cryptography==42.0.8 pyodbc==5.1.0 'moto[ec2,s3,all]'==5.0.14

# install python deps
# Tracer does not support flask 2.3.0 or higher, pin the flask version for now
RUN pip install 'flask[async]'==2.2.4 flask-login==0.6.3 gunicorn==21.2.0 gevent==24.2.1 requests==2.32.3 pycryptodome==3.20.0 psycopg2-binary==2.9.9 confluent-kafka==2.1.1 graphene==3.4.3

RUN pip install boto3==1.34.141 kombu==5.3.7 mock==5.1.0 asyncpg==0.29.0 aiomysql==0.2.0 mysql-connector-python==9.0.0 mysqlclient==2.2.4 urllib3==1.26.19 loguru==0.7.3

# Install Rust toolchain
RUN curl https://sh.rustup.rs -sSf | sh -s -- --default-toolchain stable -y
ENV PATH="/root/.cargo/bin:$PATH"

# docker build --progress=plain -f utils/build/docker/python/flask-poc.base.Dockerfile -t datadog/system-tests:flask-poc.base-v9 .
# docker push datadog/system-tests:flask-poc.base-v9

