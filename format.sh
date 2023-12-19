#!/bin/bash
set -eu

readonly BLACK_VERSION=19.10b0
readonly IMAGE=black:${BLACK_VERSION}

if [[ -z "$(docker images -q "${IMAGE}")" ]]; then
  echo "Building ${IMAGE}"
  docker build -t "${IMAGE}" - <<EOF
FROM python:3.10
RUN pip install click==7.1.2 black==${BLACK_VERSION}
EOF
fi

if [[ -z ${1:-} ]]; then
	set -- .
fi
exec docker run -it --rm --user="$(id -u):$(id -g)" --workdir "$(pwd)" -v "$(pwd):$(pwd)" "${IMAGE}" black "$@"
