# if any change here, please update AgentContainer class
ARG AGENT_IMAGE=datadog/agent:latest
FROM $AGENT_IMAGE

RUN set -eux;\
    apt-get update;\
    apt-get --no-install-recommends -y install ca-certificates --option=Dpkg::Options::=--force-confdef;\
    rm -rf /var/lib/apt/lists/*;

# Datadog agent conf
RUN echo '\
log_level: DEBUG\n\
apm_config:\n\
  apm_non_local_traffic: true\n\
  trace_buffer: 5\n\
remote_configuration:\n\
  enabled: false\n\
logs_enabled: true\n\
logs_config:\n\
  batch_wait: 1\n\
otlp_config:\n\
  debug:\n\
    verbosity: detailed\n\
  receiver:\n\
    protocols:\n\
      http:\n\
        endpoint: 0.0.0.0:4318\n\
  traces:\n\
    enabled: true\n\
    span_name_as_resource_name: true\n\
  metrics:\n\
    enabled: true\n\
    histograms:\n\
      mode: distributions\n\
      send_aggregation_metrics: true\n\
  logs:\n\
    enabled: true\n\
' >> /etc/datadog-agent/datadog.yaml

# Proxy conf
COPY utils/scripts/install_mitm_certificate.sh .
RUN set -eux;\
    mkdir -p /usr/local/share/ca-certificates;\
    ./install_mitm_certificate.sh /usr/local/share/ca-certificates/mitm.crt;\
    update-ca-certificates;

# Smoke test
RUN /opt/datadog-agent/bin/agent/agent version
