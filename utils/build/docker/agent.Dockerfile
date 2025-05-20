# if any change here, please update AgentContainer class
ARG AGENT_IMAGE=datadog/agent:latest
FROM $AGENT_IMAGE

# Datadog agent conf
RUN echo '\
log_level: DEBUG\n\
dogstatsd_non_local_traffic: true\n\
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
RUN ./install_mitm_certificate.sh /etc/ssl/certs/ca-certificates.crt;

# Smoke test
RUN /opt/datadog-agent/bin/agent/agent version
