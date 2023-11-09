import os
import json

from utils.tools import logger
from datetime import datetime, timedelta


class TestedVirtualMachine:
    def __init__(
        self,
        ec2_data,
        agent_install_data,
        language,
        autoinjection_install_data,
        autoinjection_uninstall_data,
        language_variant_install_data,
        weblog_install_data,
        weblog_uninstall_data,
        prepare_init_config_install,
        prepare_repos_install,
        prepare_docker_install,
        installation_check_data,
        provision_scenario,
        uninstall,
    ) -> None:
        self.ec2_data = ec2_data
        self.agent_install_data = agent_install_data
        self.language = language
        self.autoinjection_install_data = autoinjection_install_data
        self.autoinjection_uninstall_data = autoinjection_uninstall_data
        self.language_variant_install_data = language_variant_install_data
        self.weblog_install_data = weblog_install_data
        self.weblog_uninstall_data = weblog_uninstall_data
        self.ip = None
        self.datadog_config = None
        self.aws_infra_config = None
        self.prepare_init_config_install = prepare_init_config_install
        self.prepare_repos_install = prepare_repos_install
        self.prepare_docker_install = prepare_docker_install
        self.installation_check_data = installation_check_data
        self.provision_scenario = provision_scenario
        self.name = self.ec2_data["name"] + "__lang-variant-" + self.language_variant_install_data["name"]
        self.components = None
        # Uninstall process after install all software requirements
        self.uninstall = uninstall

        self.ami_id = None
        self.ami_name = None

    def configure(self):
        self.datadog_config = DataDogConfig()
        self.aws_infra_config = AWSInfraConfig()
        self._configure_ami()

    def start(self):
        import pulumi
        import pulumi_aws as aws
        from pulumi import Output
        import pulumi_command as command
        from utils.onboarding.pulumi_ssh import PulumiSSH
        from utils.onboarding.pulumi_utils import remote_install, pulumi_logger, remote_docker_login

        self.configure()
        # Startup VM and prepare connection
        server = aws.ec2.Instance(
            self.name,
            instance_type=self.aws_infra_config.instance_type,
            vpc_security_group_ids=self.aws_infra_config.vpc_security_group_ids,
            subnet_id=self.aws_infra_config.subnet_id,
            key_name=PulumiSSH.keypair_name,
            ami=self.ec2_data["ami_id"] if self.ami_id is None else self.ami_id,
            tags={"Name": self.name,},
            opts=PulumiSSH.aws_key_resource,
        )

        pulumi.export("privateIp_" + self.name, server.private_ip)
        Output.all(server.private_ip).apply(lambda args: self.set_ip(args[0]))
        Output.all(server.private_ip, self.name).apply(
            lambda args: pulumi_logger(self.provision_scenario, "vms_desc").info(f"{args[0]}:{args[1]}")
        )

        connection = command.remote.ConnectionArgs(
            host=server.private_ip,
            user=self.ec2_data["user"],
            private_key=PulumiSSH.private_key_pem,
            dial_error_limit=-1,
        )

        # We apply initial configurations to the VM before starting with the installation proccess
        prepare_init_config_installer = remote_install(
            connection,
            "prepare_init_config_installer_" + self.name,
            self.prepare_init_config_install["install"],
            server,
            scenario_name=self.provision_scenario,
        )

        # To launch remote task in dependency order
        main_task_dep = prepare_init_config_installer

        if self.ami_id is None:
            # Ok. The AMI doesn't exist we should create.
            # We will configure respositories, install docker and lang variant.
            # After that, we will register the new AMI to use it in the future executions

            # Prepare repositories, if we need (ie if we use agent auto install script, we don't need to prepare repos manually)
            if "install" in self.prepare_repos_install:
                prepare_repos_installer = remote_install(
                    connection,
                    "prepare-repos-installer_" + self.name,
                    self.prepare_repos_install["install"],
                    prepare_init_config_installer,
                    scenario_name=self.provision_scenario,
                )
            else:
                prepare_repos_installer = prepare_init_config_installer

            # Prepare docker installation if we need
            prepare_docker_installer = remote_install(
                connection,
                "prepare-docker-installer_" + self.name,
                self.prepare_docker_install["install"],
                prepare_repos_installer,
                scenario_name=self.provision_scenario,
            )

            # Install language variants (not mandatory)
            if "install" in self.language_variant_install_data:
                main_task_dep = remote_install(
                    connection,
                    "lang-variant-installer_" + self.name,
                    self.language_variant_install_data["install"],
                    prepare_docker_installer,
                    scenario_name=self.provision_scenario,
                )
            else:
                main_task_dep = prepare_docker_installer

            # If the ami_name is None, we can not create the AMI (Probably because there another AMI is being generating)
            if self.ami_name is not None:
                # Ok. All third party software is installed, let's create the ami to reuse it in the future
                logger.info(f"Creating AMI with name [{self.ami_name}] from instance ")
                # Expiration date for the ami
                # expiration_date = (datetime.now() + timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

                main_task_dep = aws.ec2.AmiFromInstance(
                    self.ami_name,
                    # deprecation_time=expiration_date,
                    source_instance_id=server.id,
                    opts=pulumi.ResourceOptions(depends_on=[main_task_dep], retain_on_delete=True),
                )

        else:
            logger.info("Using a previously existing AMI")

        # Docker login if we need (avoid too many requests)
        if self.prepare_docker_install["install"] is not None and self.datadog_config.docker_login:
            main_task_dep = remote_docker_login(
                "docker-login_" + self.name,
                self.datadog_config.docker_login,
                self.datadog_config.docker_login_pass,
                connection,
                main_task_dep,
            )

        # Install agent. If we are using agent autoinstall script, agent install info will be empty, due to we load the install process on auto injection node
        if "install" in self.agent_install_data:
            agent_installer = remote_install(
                connection,
                "agent-installer_" + self.name,
                self.agent_install_data["install"],
                main_task_dep,
                add_dd_keys=True,
                dd_api_key=self.datadog_config.dd_api_key,
                dd_site=self.datadog_config.dd_site,
                scenario_name=self.provision_scenario,
            )
        else:
            agent_installer = main_task_dep

        # Install autoinjection
        autoinjection_installer = remote_install(
            connection,
            "autoinjection-installer_" + self.name,
            self.autoinjection_install_data["install"],
            agent_installer,
            add_dd_keys=True,
            dd_api_key=self.datadog_config.dd_api_key,
            dd_site=self.datadog_config.dd_site,
            scenario_name=self.provision_scenario,
        )

        # Extract installed component versions
        remote_install(
            connection,
            "installation-check_" + self.name,
            self.installation_check_data["install"],
            autoinjection_installer,
            logger_name="pulumi_installed_versions",
            scenario_name=self.provision_scenario,
            output_callback=lambda command_output: self.set_components(command_output),
        )

        # Build weblog app
        weblog_runner = remote_install(
            connection,
            "run-weblog_" + self.name,
            self.weblog_install_data["install"],
            autoinjection_installer,
            add_dd_keys=True,
            dd_api_key=self.datadog_config.dd_api_key,
            dd_site=self.datadog_config.dd_site,
            scenario_name=self.provision_scenario,
        )

        # Uninstall process (stop app, uninstall autoinjection and rerun the app)
        if self.uninstall:
            logger.info(f"Uninstall the autoinjection software. Command: {self.weblog_uninstall_data['uninstall']} ")
            weblog_uninstall = remote_install(
                connection,
                "uninstall-weblog_" + self.name,
                self.weblog_uninstall_data["uninstall"],
                weblog_runner,
                scenario_name=self.provision_scenario,
            )
            autoinjection_uninstall = remote_install(
                connection,
                "uninstall-autoinjection_" + self.name,
                self.autoinjection_uninstall_data["uninstall"],
                weblog_uninstall,
                scenario_name=self.provision_scenario,
            )
            # Rerun weblog app again, but without autoinstrumentation
            weblog_rerunner = remote_install(
                connection,
                "rerun-weblog_" + self.name,
                self.weblog_install_data["install"],
                autoinjection_uninstall,
                add_dd_keys=True,
                dd_api_key=self.datadog_config.dd_api_key,
                dd_site=self.datadog_config.dd_site,
                scenario_name=self.provision_scenario,
            )

    def set_ip(self, instance_ip):
        self.ip = instance_ip

    def set_components(self, components_json):
        """Set installed software components version as json. ie {comp_name:version,comp_name2:version2...}"""
        self.components = json.loads(components_json.replace("'", '"'))

    def get_component(self, component_name):
        raw_version = self.components[component_name]
        # Workaround clean "Epoch" from debian packages.
        # The format is: [epoch:]upstream_version[-debian_revision]
        if ":" in raw_version:
            raw_version = raw_version.split(":")[1]
        return raw_version.strip()

    def _configure_ami(self):
        import pulumi_aws as aws

        # import pulumi

        # Configure name
        self.ami_name = self.name

        if "install" not in self.prepare_repos_install:
            self.ami_name = self.ami_name + "__autoinstall"

        if self.prepare_docker_install["install"] is not None:
            self.ami_name = self.ami_name + "__container"
        else:
            self.ami_name = self.ami_name + "__host"

        # Check for existing ami
        ami_existing = aws.ec2.get_ami_ids(
            filters=[aws.ec2.GetAmiIdsFilterArgs(name="name", values=[self.ami_name + "-*"],)], owners=["self"],
        )

        if len(ami_existing.ids) > 0:
            # Latest ami details
            ami_recent = aws.ec2.get_ami(
                filters=[aws.ec2.GetAmiIdsFilterArgs(name="name", values=[self.ami_name + "-*"],)],
                owners=["self"],
                most_recent=True,
            )
            logger.info(
                f"We found an existing AMI with name {self.ami_name}: [{ami_recent.id}] and status:[{ami_recent.state}] and expiration: [{ami_recent.deprecation_time}]"
            )
            # The AMI exists. We don't need to create the AMI again
            self.ami_id = ami_recent.id

            if str(ami_recent.state) != "available":
                logger.info(
                    f"We found an existing AMI but we can no use it because the current status is {ami_recent.state}"
                )
                logger.info("We are not going to create a new AMI and we are not going to use it")
                self.ami_id = None
                self.ami_name = None

            # But if we ser env var, created AMI again mandatory (TODO we should destroy previously existing one)
            if os.getenv("AMI_UPDATE") is not None:
                # TODO Pulumi is not prepared to delete resources. Workaround: Import existing ami to pulumi stack, to be deleted when destroying the stack
                # aws.ec2.Ami( ami_existing.name,
                #    name=ami_existing.name,
                #    opts=pulumi.ResourceOptions(import_=ami_existing.id))
                logger.info("We found an existing AMI but AMI_UPDATE is set. We are going to update the AMI")
                self.ami_id = None

        else:
            logger.info(f"Not found an existing AMI with name {self.ami_name}")


class AWSInfraConfig:
    def __init__(self) -> None:

        # Mandatory parameters
        self.subnet_id = os.getenv("ONBOARDING_AWS_INFRA_SUBNET_ID")
        self.vpc_security_group_ids = os.getenv("ONBOARDING_AWS_INFRA_SECURITY_GROUPS_ID", "").split(",")
        self.instance_type = os.getenv("ONBOARDING_AWS_INFRA_INSTANCE_TYPE", "t2.medium")

        if None in (self.subnet_id, self.vpc_security_group_ids):
            logger.warn("AWS infastructure is not configured correctly for auto-injection testing")


class DataDogConfig:
    def __init__(self) -> None:
        self.dd_api_key = os.getenv("DD_API_KEY_ONBOARDING")
        self.dd_app_key = os.getenv("DD_APP_KEY_ONBOARDING")
        self.docker_login = os.getenv("DOCKER_LOGIN")
        self.docker_login_pass = os.getenv("DOCKER_LOGIN_PASS")
        self.dd_site = os.getenv("DD_SITE_ONBOARDING", "datadoghq.com")
        if None in (self.dd_api_key, self.dd_app_key):
            logger.warn("Datadog agent is not configured correctly for auto-injection testing")
