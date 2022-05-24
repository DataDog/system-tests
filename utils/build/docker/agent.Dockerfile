FROM debian:10

# Install the datadog agent

RUN apt-get update && apt-get -y install \
    apt-transport-https \
    gnupg2 \
    ca-certificates

RUN echo 'deb https://apt.datadoghq.com/ stable 7' > /etc/apt/sources.list.d/datadog.list

RUN apt-key adv --recv-keys --keyserver hkp://keyserver.ubuntu.com:80 A2923DFF56EDA6E76E55E492D3A80E30382E94DE
RUN apt-key adv --recv-keys --keyserver hkp://keyserver.ubuntu.com:80 D75CEA17048B9ACBF186794B32637D44F14F620E

RUN apt-get update && apt-get -y install curl datadog-agent=1:7.35.2-1

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
RUN ./install_mitm_certificate.sh /usr/local/share/ca-certificates/mitm.crt
RUN update-ca-certificates

RUN datadog-agent version

CMD ["/opt/datadog-agent/embedded/bin/trace-agent", "-config", "/etc/datadog-agent/datadog.yaml"]
