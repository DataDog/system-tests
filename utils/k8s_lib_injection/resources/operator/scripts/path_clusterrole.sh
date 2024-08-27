#!/bin/bash

kubectl patch clusterrole datadog-cluster-agent --type='json' -p '[{"op": "add", "path": "/rules/0", "value":{ "apiGroups": ["apps"], "resources": ["deployments"], "verbs": ["patch"]}}]'