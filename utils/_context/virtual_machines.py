import os
from utils.tools import logger
import pulumi
import pulumi_aws as aws
import pulumi_command as command
from pulumi import Output

import logging
import logging.config
import os
from tests.onboarding.utils.provision_parser import Provision_parser, Provision_filter


class TestedVirtualMachine:
    def __init__(
        self,
        ec2_data,
        agent_install_data,
        language,
        autoinjection_install_data,
        language_variant_install_data,
        weblog_install_data,
        provision_filter,
    ) -> None:
        self.ec2_data = ec2_data
        self.agent_install_data = agent_install_data
        self.language = language
        self.autoinjection_install_data = autoinjection_install_data
        self.language_variant_install_data = language_variant_install_data
        self.weblog_install_data = weblog_install_data
        self.ip = None
        self.datadog_config = DataDogConfig()
        self.aws_infra_config = AWSInfraConfig()
        self.provision_filter = provision_filter
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

    def start(self):

        os_type = self.ec2_data["os_type"]
        os_distro = self.ec2_data["os_distro"]
        os_branch = self.ec2_data.get("os_branch", None)
        provision_parser = Provision_parser(self.provision_filter)

        server = aws.ec2.Instance(
            self.name,
            instance_type=self.aws_infra_config.instance_type,
            vpc_security_group_ids=self.aws_infra_config.vpc_security_group_ids,
            subnet_id=self.aws_infra_config.subnet_id,
            key_name=self.aws_infra_config.keyPairName,
            ami=self.ec2_data["ami_id"],
            tags={"Name": self.name,},
        )

        pulumi.export("privateIp_" + self.provision_filter.provision_scenario + "__" + self.name, server.private_ip)
        Output.all(server.private_ip).apply(lambda args: self.set_ip(args[0]))

        private_key_pem = (lambda path: open(path).read())(self.aws_infra_config.privateKeyPath)
        connection = command.remote.ConnectionArgs(
            host=server.private_ip, user=self.ec2_data["user"], private_key=private_key_pem, dial_error_limit=-1,
        )

        # Prepare repositories
        prepare_repos_install = provision_parser.ec2_prepare_repos_install_data(os_type, os_distro)
        prepare_repos_installer = self._remote_install(
            connection, "prepare-repos-installer_" + self.name, prepare_repos_install["install"], server
        )

        # Prepare docker installation if we need
        prepare_docker_install = provision_parser.ec2_prepare_docker_install_data(os_type, os_distro)
        prepare_docker_installer = self._remote_install(
            connection,
            "prepare-docker-installer_" + self.name,
            prepare_docker_install["install"],
            prepare_repos_installer,
        )

        # Install agent
        agent_installer = self._remote_install(
            connection,
            "agent-installer_" + self.name,
            self.agent_install_data["install"],
            prepare_docker_installer,
            add_dd_keys=True,
        )

        # Install autoinjection
        autoinjection_installer = self._remote_install(
            connection,
            "autoinjection-installer_" + self.name,
            self.autoinjection_install_data["install"],
            agent_installer,
        )

        # Extract installed component versions
        installation_check_data = provision_parser.ec2_installation_checks_data(
            self.language, os_type, os_distro, os_branch
        )
        self._remote_install(
            connection,
            "installation-check_" + self.name,
            installation_check_data["install"],
            autoinjection_installer,
            logger_name="pulumi_installed_versions",
        )

        # Install language variants (not mandatory)
        if "install" in self.language_variant_install_data:
            lang_variant_installer = self._remote_install(
                connection,
                "lang-variant-installer_" + self.name,
                self.language_variant_install_data["install"],
                autoinjection_installer,
            )
        else:
            lang_variant_installer = autoinjection_installer

        # Build weblog app
        weblog_runner = self._remote_install(
            connection,
            "run-weblog_" + self.name,
            self.weblog_install_data["install"],
            lang_variant_installer,
            add_dd_keys=True,
        )

    def _remote_install(
        self, connection, command_identifier, install_info, depends_on, add_dd_keys=False, logger_name=None
    ):
        # Do we need to add env variables?
        if install_info is None:
            return depends_on
        if add_dd_keys:
            command_exec = (
                "DD_API_KEY="
                + self.datadog_config.dd_api_key
                + " DD_SITE="
                + self.datadog_config.dd_site
                + " "
                + install_info["command"]
            )
        else:
            command_exec = install_info["command"]

        local_command = None
        # Execute local command if we need
        if "local-command" in install_info:
            local_command = install_info["local-command"]

        # Execute local script if we need
        if "local-script" in install_info:
            local_command = "sh " + install_info["local-script"]

        if local_command:
            webapp_build = command.local.Command(
                "local-script_" + command_identifier,
                create=local_command,
                opts=pulumi.ResourceOptions(depends_on=[depends_on]),
            )
            webapp_build.stdout.apply(lambda outputlog: self.pulumi_logger("build_local_weblogs").info(outputlog))
            depends_on = webapp_build

        # Copy files from local to remote if we need
        if "copy_files" in install_info:
            for file_to_copy in install_info["copy_files"]:

                # If we don't use remote_path, the remote_path will be a default remote user home
                if "remote_path" in file_to_copy:
                    remote_path = file_to_copy["remote_path"]
                else:
                    remote_path = os.path.basename(file_to_copy["local_path"])

                # Launch copy file command
                cmd_cp_webapp = command.remote.CopyFile(
                    file_to_copy["name"] + "-" + command_identifier,
                    connection=connection,
                    local_path=file_to_copy["local_path"],
                    remote_path=remote_path,
                    opts=pulumi.ResourceOptions(depends_on=[depends_on]),
                )
            depends_on = cmd_cp_webapp

        # Execute a basic command on our server.
        cmd_exec_install = command.remote.Command(
            command_identifier,
            connection=connection,
            create=command_exec,
            opts=pulumi.ResourceOptions(depends_on=[depends_on]),
        )
        if logger_name:
            cmd_exec_install.stdout.apply(lambda outputlog: self.pulumi_logger(logger_name).info(outputlog))
        else:
            # If there isn't logger name specified, we will use the host/ip name to store all the logs of the
            # same remote machine in the same log file
            Output.all(connection.host, cmd_exec_install.stdout).apply(
                lambda args: self.pulumi_logger(args[0]).info(args[1])
            )

        return cmd_exec_install

    def pulumi_logger(self, log_name, level=logging.INFO):
        formatter = logging.Formatter("%(message)s")
        handler = logging.FileHandler(f"logs_onboarding/{log_name}.log")
        handler.setFormatter(formatter)
        specified_logger = logging.getLogger(log_name)
        specified_logger.setLevel(level)
        specified_logger.addHandler(handler)
        return specified_logger

    def set_ip(self, instance_ip):
        self.ip = instance_ip


class AWSInfraConfig:
    def __init__(self) -> None:
        self.keyPairName = os.getenv("ONBOARDING_AWS_INFRA_KEYPAIR_NAME")
        self.subnet_id = os.getenv("ONBOARDING_AWS_INFRA_SUBNET_ID")
        self.vpc_security_group_ids = os.getenv("ONBOARDING_AWS_INFRA_SECURITY_GROUPS_ID", "").split(",")
        self.privateKeyPath = os.getenv("ONBOARDING_AWS_INFRA_KEY_PATH")
        self.instance_type = os.getenv("ONBOARDING_AWS_INFRA_INSTANCE_TYPE", "t2.medium")

        if None in (self.keyPairName, self.subnet_id, self.vpc_security_group_ids, self.privateKeyPath):
            raise ValueError("AWS infastructure is not configured correctly")


class DataDogConfig:
    def __init__(self) -> None:
        self.dd_api_key = os.getenv("DD_API_KEY")
        self.dd_app_key = os.getenv("DD_APP_KEY")
        self.dd_site = os.getenv("DD_SITE", "datadoghq.com")
        if None in (self.dd_api_key, self.dd_app_key):
            raise ValueError("Datadog agent is not configured correctly")
