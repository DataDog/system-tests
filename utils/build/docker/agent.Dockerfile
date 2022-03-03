ARG AGENT_IMAGE=datadog/agent:7
FROM $AGENT_IMAGE

RUN apt-get update && apt-get -y install \
    apt-transport-https \
    gnupg2 \
    ca-certificates

# Datadog agent conf

RUN touch /etc/datadog-agent/datadog.yaml
RUN echo '\
log_level: DEBUG\n\
apm_config:\n\
  apm_non_local_traffic: true\n\
proxy:\n\
    http: "http://agent_proxy:8082"\n\
    https: "http://agent_proxy:8082"\n\
    no_proxy_nonexact_match: false\n\
' >> /etc/datadog-agent/datadog.yaml

# Proxy conf
COPY utils/scripts/install_mitm_certificate.sh .
RUN mkdir -p /usr/local/share/ca-certificates
RUN ./install_mitm_certificate.sh /usr/local/share/ca-certificates/mitm.crt
RUN update-ca-certificates

RUN /opt/datadog-agent/bin/agent/agent version

HEALTHCHECK --interval=10s --timeout=5s --retries=6 CMD [ "curl", "-f", "http://localhost:8126/info" ]

CMD ["/opt/datadog-agent/embedded/bin/trace-agent", "-config", "/etc/datadog-agent/datadog.yaml"]
