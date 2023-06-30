FROM mitmproxy/mitmproxy:9.0.1

RUN pip install requests-toolbelt==1.0.0 grpcio-tools==1.56.0 opentelemetry-proto==1.17.0
