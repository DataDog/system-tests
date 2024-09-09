#!/bin/bash
# shellcheck disable=SC2116,SC2086
export DD_APM_INSTRUMENTATION_DEBUG=false
DD_LANG=$1

if [ "$DD_LANG" == "java" ]; then
    java_version=$(java -version 2>&1)
    runtime_version=$(echo "$java_version" | grep version | awk '{print $3}' | tr -d '"')
fi

if [ -f /etc/debian_version ] || [ "$DISTRIBUTION" = "Debian" ] || [ "$DISTRIBUTION" = "Ubuntu" ]; then
      if dpkg -s datadog-agent &> /dev/null; then
        agent_version=$(dpkg -s datadog-agent | grep Version  | head -n 1);
        agent_version=${agent_version//'Version:'/}
      else
        agent_path="$(readlink -f /opt/datadog-packages/datadog-agent/stable)"
        agent_path="${agent_path%/}"
        agent_version="${agent_path##*/}"
        agent_version="${agent_version%-1}"
      fi

      if dpkg -s datadog-apm-inject &> /dev/null; then
        inject_version=$(dpkg -s datadog-apm-inject | grep Version);
        inject_version=${inject_version//'Version:'/}
      else
        inject_path="$(readlink -f /opt/datadog-packages/datadog-apm-inject/stable)"
        inject_path="${inject_path%/}"
        inject_version="${inject_path##*/}"
        inject_version="${inject_version%-1}"
      fi

      if dpkg -s datadog-apm-library-$DD_LANG &> /dev/null; then
        tracer_version=$(dpkg -s datadog-apm-library-$DD_LANG | grep Version);
        tracer_version=${tracer_version//'Version:'/}
      else
        tracer_path="$(readlink -f /opt/datadog-packages/datadog-apm-library-$DD_LANG/stable)"
        tracer_path="${tracer_path%/}"
        tracer_version="${tracer_path##*/}"
        tracer_version="${tracer_version%-1}"
      fi

      installer_path="$(readlink -f /opt/datadog-packages/datadog-installer/stable)"
      installer_path="${installer_path%/}"
      installer_version="${installer_path##*/}"
      installer_version="${installer_version%-1}"

      echo "{'weblog_url':'$(echo $WEBLOG_URL)','runtime_version':'$(echo $runtime_version)','agent':'$(echo $agent_version)','datadog-apm-inject':'$(echo $inject_version)','datadog-apm-library-$DD_LANG': '$(echo $tracer_version)','docker':'$(docker -v || true)','datadog-installer':'$(echo $installer_version)'}"

elif [ -f /etc/redhat-release ] || [ "$DISTRIBUTION" = "RedHat" ] || [ "$DISTRIBUTION" = "CentOS" ] || [ "$DISTRIBUTION" = "Amazon" ] || [ "$DISTRIBUTION" = "Rocky" ] || [ "$DISTRIBUTION" = "AlmaLinux" ]; then
      if [ -n "$(rpm -qa --queryformat '%{VERSION}-%{RELEASE}' datadog-agent)" ]; then
        agent_version=$(rpm -qa --queryformat '%{VERSION}-%{RELEASE}' datadog-agent);
      else
        agent_path="$(readlink -f /opt/datadog-packages/datadog-agent/stable)"
        agent_path="${agent_path%/}"
        agent_version="${agent_path##*/}"
        agent_version="${agent_version%-1}"
      fi

      if [ -n "$(rpm -qa --queryformat '%{VERSION}-%{RELEASE}' datadog-apm-inject)" ]; then
        inject_version=$(rpm -qa --queryformat '%{VERSION}-%{RELEASE}' datadog-apm-inject);
      else
        inject_path="$(readlink -f /opt/datadog-packages/datadog-apm-inject/stable)"
        inject_path="${inject_path%/}"
        inject_version="${inject_path##*/}"
        inject_version="${inject_version%-1}"
      fi

      if [ -n "$(rpm -qa --queryformat '%{VERSION}-%{RELEASE}' datadog-apm-library-$DD_LANG)" ]; then
        tracer_version=$(rpm -qa --queryformat '%{VERSION}-%{RELEASE}' datadog-apm-library-$DD_LANG);
      else
        tracer_path="$(readlink -f /opt/datadog-packages/datadog-apm-library-$DD_LANG/stable)"
        tracer_path="${tracer_path%/}"
        tracer_version="${tracer_path##*/}"
        tracer_version="${tracer_version%-1}"
      fi

      installer_path="$(readlink -f /opt/datadog-packages/datadog-installer/stable)"
      installer_path="${installer_path%/}"
      installer_version="${installer_path##*/}"
      installer_version="${installer_version%-1}"

      echo "{'runtime_version':'$(echo $runtime_version)','agent':'$(echo $agent_version)','datadog-apm-inject':'$(echo $inject_version)','datadog-apm-library-$DD_LANG': '$(echo $tracer_version)','docker':'$(docker -v || true)','datadog-installer':'$(echo $installer_version)'}"
else
   echo "NO_SUPPORTED"
fi