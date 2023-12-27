FROM python:3.9


RUN mkdir /app
WORKDIR /app

COPY utils/build/docker/python/parametric/requirements.txt utils/build/docker/python/parametric/requirements.txt
COPY requirements.txt .
COPY build.sh .
COPY utils/build/build.sh utils/build/build.sh
RUN mkdir -p /app/utils/build/docker && ./build.sh -i runner

# tests
COPY tests /app/tests
COPY parametric /app/parametric

# basically everything except utils/build
COPY utils/parametric /app/utils/parametric
COPY utils/onboarding /app/utils/onboarding
COPY utils/_context /app/utils/_context
COPY utils/assets /app/utils/assets
COPY utils/grpc /app/utils/grpc
COPY utils/proxy /app/utils/proxy
COPY utils/interfaces /app/utils/interfaces
COPY utils/scripts /app/utils/scripts
COPY utils/*.py /app/utils/

# toplevel things
COPY conftest.py /app/
COPY pyproject.toml /app/
COPY run.sh /app/

CMD ./run.sh
