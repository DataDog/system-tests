FROM python:3.12

RUN mkdir /app
WORKDIR /app

COPY utils/build/docker/python/parametric/requirements.txt utils/build/docker/python/parametric/requirements.txt
COPY requirements.txt .
COPY build.sh .
COPY utils/build/build.sh utils/build/build.sh
RUN mkdir -p /app/utils/build/docker && ./build.sh -i runner


COPY utils/ /app/utils/
# tests
COPY tests /app/tests
COPY parametric /app/parametric


# manifests
COPY manifests /app/manifests

# toplevel things
COPY conftest.py /app/
COPY pyproject.toml /app/
COPY run.sh /app/

CMD ./run.sh
