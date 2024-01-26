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

# Run as the current user, but only if docker is not "rootless".
# To determine whether docker is rootless, examine the permissions of the file
# referred to by DOCKER_HOST. If it's owned by the current user, then assume
# that docker is rootless.
DOCKER_HOST="${DOCKER_HOST:-}"
if [[ "${DOCKER_HOST}" == unix://* && -O "${DOCKER_HOST#unix://}" ]]; then
  user_arg=""
else
  user_arg="--user=$(id -u):$(id -g)"
fi

# shellcheck disable=SC2086
exec docker run -it --rm $user_arg --workdir "$(pwd)" -v "$(pwd):$(pwd)" "${IMAGE}" black "$@"
