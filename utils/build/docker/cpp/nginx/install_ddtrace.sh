#!/bin/bash

set -eu

get_latest_release() {
    wget -qO- "https://api.github.com/repos/$1/releases/latest" | jq -r '.tag_name'
}

NGINX_VERSION=1.17.3

OPENTRACING_NGINX_VERSION="$(get_latest_release opentracing-contrib/nginx-opentracing)"
DD_OPENTRACING_CPP_VERSION="$(get_latest_release DataDog/dd-opentracing-cpp)"

echo "opentracing-contrib/nginx-opentracing version: $OPENTRACING_NGINX_VERSION"
echo "DataDog/dd-opentracing-cpp version: $DD_OPENTRACING_CPP_VERSION"
echo $DD_OPENTRACING_CPP_VERSION > SYSTEM_TESTS_LIBRARY_VERSION
touch SYSTEM_TESTS_LIBDDWAF_VERSION
echo "0.0.0" > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

# Install NGINX plugin for OpenTracing
wget https://github.com/opentracing-contrib/nginx-opentracing/releases/download/${OPENTRACING_NGINX_VERSION}/linux-amd64-nginx-${NGINX_VERSION}-ot16-ngx_http_module.so.tgz
tar zxf linux-amd64-nginx-${NGINX_VERSION}-ot16-ngx_http_module.so.tgz -C /usr/lib/nginx/modules
# Install Datadog Opentracing C++ Plugin
wget https://github.com/DataDog/dd-opentracing-cpp/releases/download/${DD_OPENTRACING_CPP_VERSION}/linux-amd64-libdd_opentracing_plugin.so.gz
gunzip linux-amd64-libdd_opentracing_plugin.so.gz -c > /usr/local/lib/libdd_opentracing_plugin.so

echo "Library version : $(cat SYSTEM_TESTS_LIBRARY_VERSION)"