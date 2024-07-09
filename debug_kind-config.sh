#!/usr/bin/env bash

echo "STEP 1"
kind create cluster --image=kindest/node:v1.25.3@sha256:f52781bc0d7a19fb6c405c2af83abfeb311f130707a0e219175677e366cc45d1 --name lib-injection-testing --config debug_kind-config.yaml --wait 1m 
echo "STEP  2"
