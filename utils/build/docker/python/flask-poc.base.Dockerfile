FROM python:3.9-slim

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
    
#pip install driver pymysql and pyodbc(mssql)
RUN pip install pymysql cryptography pyodbc

# install python deps
# Tracer does not support flask 2.3.0 or higher, pin the flask version for now
RUN pip install flask==2.2.4 gunicorn gevent requests pycryptodome psycopg2-binary confluent-kafka==2.1.1

# docker build --progress=plain -f utils/build/docker/python/flask-poc.base.Dockerfile -t datadog/system-tests:flask-poc.base-v2 .
# docker push datadog/system-tests:flask-poc.base-v2

