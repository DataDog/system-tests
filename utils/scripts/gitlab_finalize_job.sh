#!/bin/bash
#
# after_script entry point of the Docker SSI, AWS SSI and K8s lib injection GitLab jobs.
# All the logic lives in gitlab_finalize_job.py.
#
# Usage:
#   gitlab_finalize_job.sh --profile <docker|aws|k8s>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEM_TESTS_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# The virtualenv is missing when the job fails before ./build.sh creates it.
PYTHON="${SYSTEM_TESTS_DIR}/venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="python3"
fi

exec "${PYTHON}" -u "${SCRIPT_DIR}/gitlab_finalize_job.py" "$@"
