#!/bin/bash
#
# Tag the current GitLab pipeline so Green CI skips the AWS AMI refresh.
# The job that calls this script runs only when AMI_UPDATE=true.
# This check keeps a manual run from tagging any other pipeline.
# A Datadog API failure must not fail the AMI refresh.

set -euo pipefail

if [[ "${AMI_UPDATE:-}" != "true" ]]; then
  echo "AMI_UPDATE is not true. This pipeline stays in Green CI."
  exit 0
fi

export DATADOG_SITE="${DATADOG_SITE:-datadoghq.com}"

if ! DATADOG_API_KEY="$(read-system-tests-secret test_optimization dd_api_key)"; then
  echo "Could not read the Datadog API key. This pipeline stays in Green CI. The AMI refresh continues."
  exit 0
fi
export DATADOG_API_KEY

if ! datadog-ci tag --level pipeline --tags "green_ci.excluded:true"; then
  echo "Could not tag this pipeline for Green CI. The AMI refresh continues."
fi
