#!/usr/bin/env bash
# Run a command without the secrets that the CI platform puts in the environment of every job.
#
# In CI, the test runner fails if a secret is present in its environment (see utils/proxy/scrubber.py).
# Wrap system-tests commands with this script, e.g. utils/ci/without_ci_secrets.sh ./run.sh DEFAULT
#
# Only list here secrets that the CI platform injects on its own, or that the job needs for something else
# than system-tests. Secrets set on purpose for a job must be removed from that job instead.
# * GitLab: CI_JOB_TOKEN, CI_JOB_JWT*, CI_*_PASSWORD, CI_RUNNER_SHORT_TOKEN (set by GitLab), DD_STS_OIDC_TOKEN
#   (id_tokens, for dd-sts), DD_API_KEY (from dd-sts, for datadog-ci, see utils/ci/gitlab/templates.yml)
# * GitHub: ACTIONS_ID_TOKEN_REQUEST_TOKEN/_URL (jobs with id-token: write, for the datadog_ci action)

set -eu

exec env \
    -u CI_JOB_TOKEN \
    -u CI_JOB_JWT \
    -u CI_JOB_JWT_V1 \
    -u CI_JOB_JWT_V2 \
    -u CI_REGISTRY_PASSWORD \
    -u CI_DEPENDENCY_PROXY_PASSWORD \
    -u CI_DEPLOY_PASSWORD \
    -u CI_RUNNER_SHORT_TOKEN \
    -u DD_STS_OIDC_TOKEN \
    -u DD_API_KEY \
    -u ACTIONS_ID_TOKEN_REQUEST_TOKEN \
    -u ACTIONS_ID_TOKEN_REQUEST_URL \
    "$@"
