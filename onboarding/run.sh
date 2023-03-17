#!/bin/bash
rm pulumi.log || true
./run_tests.sh "$@"

# .:: Destroy infraestructure ::.
aws-vault exec sandbox-account-admin -- pulumi destroy --yes -C . -s dev