#!/usr/bin/env bash

# buddies are weblog app in another lang
# they are used in the CROSSED_INTEGRATIONS scenario, where we can tests data propagation between different languages 

docker build -t system_tests/python_buddy -f utils/build/docker/python/flask-poc.Dockerfile .