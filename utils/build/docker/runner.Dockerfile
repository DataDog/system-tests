FROM python:3.9


RUN mkdir /app
WORKDIR /app

COPY utils/build/docker/python/parametric/requirements.txt utils/build/docker/python/parametric/requirements.txt
COPY requirements.txt .
COPY build.sh .
COPY utils/build/build.sh utils/build/build.sh
RUN mkdir -p /app/utils/build/docker && ./build.sh -i runner

# basically everything except utils/build
COPY utils/assets /app/utils/assets
COPY utils/build /app/utils/build
COPY utils/_context /app/utils/_context
COPY utils/grpc /app/utils/grpc
COPY utils/interfaces /app/utils/interfaces
COPY utils/k8s_lib_injection /app/utils/k8s_lib_injection
COPY utils/onboarding /app/utils/onboarding
COPY utils/parametric /app/utils/parametric
COPY utils/proxy /app/utils/proxy
COPY utils/scripts /app/utils/scripts
COPY utils/virtual_machine /app/utils/virtual_machine
COPY utils/otel_validators /app/utils/otel_validators
COPY utils/*.py /app/utils/

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
