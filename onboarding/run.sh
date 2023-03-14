#!/bin/bash

ARGS=$*

# ..:: Params ::..
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -kp|--KeyPairName) AWS_KEY_PAIR_NAME="$2"; shift ;;
        -sn|--subnet) AWS_SUBNET="$2"; shift ;;
        -vpc|--vpc) AWS_VPC="$2"; shift ;;
        -s|--dd-site) DD_SITE="$2"; shift ;;
        -pk|--private-key-path) AWS_PRIVATE_KEY_PATH="$2"; shift ;;
        -it|--instance-type) AWS_INSTANCE_TYPE="$2"; shift ;;
        *) cat README.md; exit 1 ;;
    esac
    shift
done

# .:: Launch infraestructure ::.

aws-vault exec sandbox-account-admin -- pulumi up --yes \
    -c ddinfra:aws/defaultKeyPairName=$AWS_KEY_PAIR_NAME \
    -c ddinfra:aws/subnet_id=$AWS_SUBNET \
    -c ddinfra:aws/vpc_security_group_ids=$AWS_VPC \
    -c ddagent:site=$DD_SITE \
    -c ddinfra:aws/defaultPrivateKeyPath=$AWS_PRIVATE_KEY_PATH \
    -c ddinfra:aws/instance_type=$AWS_INSTANCE_TYPE \
    -C . -s dev
#For Verbose add those params to pulumi up:--logtostderr --logflow -v=9

echo "Export private IPs "
pulumi stack output --json > pulumi.output.json 

# .:: Launch tests ::.

export DD_APP_KEY=$(pulumi config get ddagent:appKey)
export DD_API_KEY=$(pulumi config get ddagent:apiKey) 
PARENT_DIR=$(dirname $PWD)
venv/bin/pytest -s -c $PWD/conftest.py tests/test_traces.py --json-report
###venv/bin/python -m pytest -s -c $PWD/conftest.py $ARGS

# .:: Destroy infraestructure ::.
aws-vault exec sandbox-account-admin -- pulumi destroy --yes -C . -s dev