FROM python:3.13-slim

# install bin dependancies
RUN apt-get update && apt-get install -y curl

# print versions
RUN python --version && curl --version
# install python deps
ENV PIP_ROOT_USER_ACTION=ignore
RUN pip install --upgrade pip
RUN pip install fastapi[standard]==0.116.1

WORKDIR /app
COPY utils/build/docker/internal_server/app.py /app


# run application
EXPOSE  8089
CMD python -m fastapi run --port 8089

# docker build --progress=plain -f utils/build/docker/internal_server/internal_server.Dockerfile -t datadog/system-tests/internal_server_v1 .
# docker run -p 8089:8089 datadog/system-tests/internal_server_v1


