FROM arm32v7/python:3.9

# print versions
RUN python --version && curl --version

# install hello world app
RUN pip install flask gunicorn

COPY utils/build/docker/python/flask.py app.py
ENV FLASK_APP=app.py

COPY utils/build/docker/python/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh

# docker startup
COPY ./utils/build/docker/python/app.sh app.sh
CMD ["./app.sh", "GUNICORN"]

# docker build -f utils/build/docker/python.flask-poc.Dockerfile -t test .
# docker run -ti -p 7777:7777 test

