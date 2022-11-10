FROM mitmproxy/mitmproxy AS mitm
WORKDIR /mitm
COPY utils/proxy/forwarder.py /mitm/
COPY utils/build/docker/tools/library_proxy.entrypoint.sh /mitm/
