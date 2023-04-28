FROM mitmproxy/mitmproxy:latest

WORKDIR /app

COPY utils/proxy /app/utils/proxy

CMD python utils/proxy/core.py

