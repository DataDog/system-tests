import os
from random import randint

import pulumi
import pulumi_aws as aws
import pulumi_tls as tls
from utils.tools import logger


class PulumiSSH:
    keypair_name = None
    private_key_pem = None
    aws_key_resource = None

    @staticmethod
    def load():
        # Optional parameters. You can use for local testing
        user_provided_keyPairName = os.getenv("ONBOARDING_AWS_INFRA_KEYPAIR_NAME")
        user_provided_privateKeyPath = os.getenv("ONBOARDING_AWS_INFRA_KEY_PATH")
        # SSH Keys: Two options. 1. Use your own keypair and pem file. 2.
        # Create a new one and automatically destroy after the test
        if user_provided_keyPairName and user_provided_privateKeyPath:
            logger.info("Using a existing key pair")
            PulumiSSH.keypair_name = user_provided_keyPairName
            with open(user_provided_privateKeyPath, encoding="utf-8") as f:
                PulumiSSH.private_key_pem = f.read()
        else:
            logger.info("Creating new ssh key")
            key_name = "onboarding_test_key_name" + str(randint(0, 1000000))
            ssh_key = tls.PrivateKey(key_name, algorithm="RSA", rsa_bits=4096)
            PulumiSSH.private_key_pem = ssh_key.private_key_pem
            aws_key = aws.ec2.KeyPair(
                key_name,
                key_name=key_name,
                public_key=ssh_key.public_key_openssh,
                opts=pulumi.ResourceOptions(parent=ssh_key),
            )
            PulumiSSH.keypair_name = aws_key.key_name
            PulumiSSH.aws_key_resource = pulumi.ResourceOptions(depends_on=[aws_key])
