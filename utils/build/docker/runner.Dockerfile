FROM python:3.12

RUN mkdir /app
WORKDIR /app

RUN mkdir tests/ manifests/

COPY utils/build/docker/python/parametric/requirements.txt utils/build/docker/python/parametric/requirements.txt
COPY requirements.txt .
COPY pyproject.toml .
COPY build.sh .
COPY utils/build/build.sh utils/build/build.sh
RUN mkdir -p /app/utils/build/docker && ./build.sh -i runner


COPY utils/ /app/utils/
# tests
COPY tests /app/tests

# manifests
COPY manifests /app/manifests

# toplevel things
COPY conftest.py /app/
COPY run.sh /app/

CMD ./run.sh
