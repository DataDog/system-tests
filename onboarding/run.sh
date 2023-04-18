#!/bin/bash
rm pulumi.log || true
rm pulumi_installed_versions || true

./run_tests.sh "$@"

#Exit 8 custom output for run_tests.sh == Invalid parameter
[[ "$?" == "8" ]] && exit 1

# .:: Destroy infraestructure ::.
aws-vault exec sandbox-account-admin -- pulumi destroy --yes -C . -s dev