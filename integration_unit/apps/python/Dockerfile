
FROM datadog/dd-trace-py:buster
WORKDIR /client
RUN pyenv global 3.9.11
RUN python3.9 -m pip install grpcio==1.46.3 grpcio-tools==1.46.3
RUN python3.9 -m pip install ddtrace
