#!/bin/bash
grep 'name = "datadog-opentelemetry"' ./Cargo.lock -A 1 | grep -Po 'version = "\K.*?(?=")'
