#!/bin/sh

set -eu

export DD_LAMBDA_HANDLER=handler.lambda_handler

# Only the SCA scenario mounts this language's catalog. Install it before
# starting the Lambda wrapper, which initializes reachability instrumentation.
if [ -f /sca_advisories.json ]; then
    python3 - <<'PY'
from pathlib import Path
from shutil import copyfile

data_paths = list(Path("/opt/python").glob("lib/python*/site-packages/ddtrace/appsec/sca/_cve_data.json"))
if len(data_paths) != 1:
    raise RuntimeError(f"Expected one bundled SCA catalog, found {data_paths}")
copyfile("/sca_advisories.json", data_paths[0])
PY
fi

socat TCP-LISTEN:8127,reuseaddr,fork,bind=0.0.0.0 TCP:127.0.0.1:8126 &

exec /lambda-entrypoint.sh datadog_lambda.handler.handler
