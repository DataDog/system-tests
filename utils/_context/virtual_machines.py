import os
from utils.tools import logger
import pulumi
import pulumi_aws as aws
from pulumi import Output
import pulumi_command as command
from utils.onboarding.pulumi_utils import remote_install, pulumi_logger


class TestedVirtualMachine:
    def __init__(
        self,
        ec2_data,
        agent_install_data,
        language,
        autoinjection_install_data,
        language_variant_install_data,
        weblog_install_data,
        prepare_repos_install,
        prepare_docker_install,
        installation_check_data,
    ) -> None:
        self.ec2_data = ec2_data
        self.agent_install_data = agent_install_data
        self.language = language
        self.autoinjection_install_data = autoinjection_install_data
        self.language_variant_install_data = language_variant_install_data
        self.weblog_install_data = weblog_install_data
        self.ip = None
        self.datadog_config = None
        self.aws_infra_config = None
        self.prepare_repos_install = prepare_repos_install
        self.prepare_docker_install = prepare_docker_install
        self.installation_check_data = installation_check_data
        self.name = (
            self.ec2_data["name"]
            + "__agent-"
            + self.agent_install_data["env"]
            + "__autoinjection-"
            + self.language
            + "-"
            + self.autoinjection_install_data["env"]
            + "__lang-variant-"
            + self.language_variant_install_data["name"]
            + "__weblog-"
            + self.weblog_install_data["name"]
        )

    def configure(self):
        self.datadog_config = DataDogConfig()
        self.aws_infra_config = AWSInfraConfig()

    def start(self):
        logger.info("start...")
        self.configure()

        logger.info("SUBNETS ID")
        logger.info(aws.ec2.get_subnet(id=self.aws_infra_config.vpc_id))
        server = aws.ec2.Instance(
            self.name,
            instance_type=self.aws_infra_config.instance_type,
            vpc_security_group_ids=self.aws_infra_config.vpc_security_group_ids,
            subnet_id=self.aws_infra_config.subnet_id,
            key_name=self.aws_infra_config.keyPairName,
            ami=self.ec2_data["ami_id"],
            tags={"Name": self.name,},
        )

        pulumi.export("privateIp_" + self.name, server.private_ip)
        Output.all(server.private_ip).apply(lambda args: self.set_ip(args[0]))
        Output.all(server.private_ip).apply(lambda args: pulumi_logger("vms_desc").info(f"{args[0]}:{self.name}"))

        private_key_pem = (lambda path: open(path).read())(self.aws_infra_config.privateKeyPath)
        connection = command.remote.ConnectionArgs(
            host=server.private_ip, user=self.ec2_data["user"], private_key=private_key_pem, dial_error_limit=-1,
        )

        # Prepare repositories
        prepare_repos_installer = remote_install(
            connection, "prepare-repos-installer_" + self.name, self.prepare_repos_install["install"], server
        )

        # Prepare docker installation if we need
        prepare_docker_installer = remote_install(
            connection,
            "prepare-docker-installer_" + self.name,
            self.prepare_docker_install["install"],
            prepare_repos_installer,
        )

        # Install agent
        agent_installer = remote_install(
            connection,
            "agent-installer_" + self.name,
            self.agent_install_data["install"],
            prepare_docker_installer,
            add_dd_keys=True,
            dd_api_key=self.datadog_config.dd_api_key,
            dd_site=self.datadog_config.dd_site,
        )

        # Install autoinjection
        autoinjection_installer = remote_install(
            connection,
            "autoinjection-installer_" + self.name,
            self.autoinjection_install_data["install"],
            agent_installer,
        )

        # Extract installed component versions
        remote_install(
            connection,
            "installation-check_" + self.name,
            self.installation_check_data["install"],
            autoinjection_installer,
            logger_name="pulumi_installed_versions",
        )

        # Install language variants (not mandatory)
        if "install" in self.language_variant_install_data:
            lang_variant_installer = remote_install(
                connection,
                "lang-variant-installer_" + self.name,
                self.language_variant_install_data["install"],
                autoinjection_installer,
            )
        else:
            lang_variant_installer = autoinjection_installer

        # Build weblog app
        weblog_runner = remote_install(
            connection,
            "run-weblog_" + self.name,
            self.weblog_install_data["install"],
            lang_variant_installer,
            add_dd_keys=True,
            dd_api_key=self.datadog_config.dd_api_key,
            dd_site=self.datadog_config.dd_site,
        )

    def set_ip(self, instance_ip):
        self.ip = instance_ip


class AWSInfraConfig:
    def __init__(self) -> None:
        self.keyPairName = os.getenv("ONBOARDING_AWS_INFRA_KEYPAIR_NAME")
        self.subnet_id = os.getenv("ONBOARDING_AWS_INFRA_SUBNET_ID")
        self.vpc_security_group_ids = os.getenv("ONBOARDING_AWS_INFRA_SECURITY_GROUPS_ID", "").split(",")
        self.privateKeyPath = os.getenv("ONBOARDING_AWS_INFRA_KEY_PATH")
        self.instance_type = os.getenv("ONBOARDING_AWS_INFRA_INSTANCE_TYPE", "t2.medium")
        self.vpc_id = os.getenv("ONBOARDING_AWS_INFRA_VPC_ID")

        if None in (self.keyPairName, self.subnet_id, self.vpc_security_group_ids, self.privateKeyPath):
            logger.warn("AWS infastructure is not configured correctly for auto-injection testing")


class DataDogConfig:
    def __init__(self) -> None:
        self.dd_api_key = os.getenv("DD_API_KEY_ONBOARDING")
        self.dd_app_key = os.getenv("DD_APP_KEY_ONBOARDING")
        self.dd_site = os.getenv("DD_SITE_ONBOARDING", "datadoghq.com")
        if None in (self.dd_api_key, self.dd_app_key):
            logger.warn("Datadog agent is not configured correctly for auto-injection testing")
