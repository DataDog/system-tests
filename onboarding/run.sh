#!/bin/bash
rm pulumi.log || true
rm logs/pulumi_installed_versions.log || true
rm -rf logs/ || true
mkdir logs/

./run_tests.sh "$@"

#Exit 8 custom output for run_tests.sh == Invalid parameter
[[ "$?" == "8" ]] && exit 1

# .:: Destroy infraestructure ::.
aws-vault exec sandbox-account-admin -- pulumi destroy --yes -C . -s dev