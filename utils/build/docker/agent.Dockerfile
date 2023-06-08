ARG AGENT_IMAGE=datadog/agent
FROM $AGENT_IMAGE

RUN apt-get update
RUN apt-get -y install apt-transport-https gnupg2
RUN apt-get -y install ca-certificates --option=Dpkg::Options::=--force-confdef

# Datadog agent conf
RUN touch /etc/datadog-agent/datadog.yaml
RUN echo '\
log_level: DEBUG\n\
apm_config:\n\
  apm_non_local_traffic: true\n\
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
      send_count_sum_metrics: true\n\
' >> /etc/datadog-agent/datadog.yaml

# Proxy conf
COPY utils/scripts/install_mitm_certificate.sh .
RUN mkdir -p /usr/local/share/ca-certificates
RUN ./install_mitm_certificate.sh /usr/local/share/ca-certificates/mitm.crt
RUN update-ca-certificates

RUN /opt/datadog-agent/bin/agent/agent version
