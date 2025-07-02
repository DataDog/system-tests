FROM python:3.11-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl git gcc g++ make cmake

# print versions
RUN python --version && curl --version

# this is necessary for the mysqlclient install
RUN apt update && apt install -y pkg-config default-libmysqlclient-dev pkg-config

# install python deps
# Tracer does not support flask 2.3.0 or higher, pin the flask version for now
RUN pip install --upgrade pip
RUN pip install 'flask[async]'==3.1.1 flask-login==0.6.3 requests==2.32.4 pycryptodome==3.23.0 psycopg2-binary==2.9.10 confluent-kafka==2.10.1 graphene==3.4.3
RUN git clone https://github.com/urllib3/urllib3.git; cd urllib3; \
    git checkout 2.5.0; \
    pip install .
RUN git clone https://github.com/unbit/uwsgi.git; cd uwsgi; \
    git checkout 2.0.30; \
    python3 uwsgiconfig.py --plugin plugins/python; \
    pip install .
RUN pip install 'moto[ec2,s3,all]'==5.1.6
RUN pip install boto3==1.39.1 kombu==5.5.4 mock==5.2.0 asyncpg==0.30.0 aiomysql==0.2.0 mysql-connector-python==9.3.0 mysqlclient==2.2.7 PyMySQL==1.1.1

# Install Rust toolchain
RUN curl https://sh.rustup.rs -sSf | sh -s -- --default-toolchain stable -y
ENV PATH="/root/.cargo/bin:$PATH"

# docker build --progress=plain -f utils/build/docker/python/uwsgi-poc.base.Dockerfile -t datadog/system-tests:uwsgi-poc.base-v6 .
# docker push datadog/system-tests:uwsgi-poc.base-v6

