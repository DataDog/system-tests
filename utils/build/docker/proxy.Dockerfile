# please update requirements.txt if you change this version
FROM mitmproxy/mitmproxy:9.0.1

WORKDIR /app

RUN pip install requests-toolbelt==1.0.0 grpcio-tools==1.56.0 opentelemetry-proto==1.17.0

COPY utils/proxy /app/utils/proxy

CMD python utils/proxy/core.py
