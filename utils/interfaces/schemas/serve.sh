# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

set -e

docker build -f ./utils/interfaces/schemas/Dockerfile -t schemas-doc-server .
docker run -p 7070:80 schemas-doc-server