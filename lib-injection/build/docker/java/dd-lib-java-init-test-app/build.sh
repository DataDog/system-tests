#!/bin/bash

docker build --tag ${LIBRARY_INJECTION_TEST_APP_IMAGE} .
docker push ${LIBRARY_INJECTION_TEST_APP_IMAGE}