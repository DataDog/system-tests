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
proxy:\n\
    http: "http://agent_proxy:8082"\n\
    https: "http://agent_proxy:8082"\n\
' >> /etc/datadog-agent/datadog.yaml

# Proxy conf
COPY utils/scripts/install_mitm_certificate.sh .
RUN mkdir -p /usr/local/share/ca-certificates
RUN ./install_mitm_certificate.sh /usr/local/share/ca-certificates/mitm.crt
RUN update-ca-certificates

RUN /opt/datadog-agent/bin/agent/agent version
