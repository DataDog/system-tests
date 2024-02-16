import os
import json
from utils.tools import logger
from datetime import datetime, timedelta

from utils.onboarding.pulumi_utils import remote_install
from utils._context.library_version import Version
from utils import context


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
        is_uninstall,
        env,
        weblog_name,
        dd_config_distro,
        is_auto_install,
        is_container,
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
        self.is_uninstall = is_uninstall
        self.env = env
        self.weblog_name = weblog_name
        self.ami_id = None
        self.ami_name = None
        self.pytestmark = self._configure_pytest_mark()
        self.dd_config_distro = dd_config_distro
        self.is_auto_install = is_auto_install
        self.is_container = is_container

        self.ec2_server = None
        self.ec2_server_connection = None

    def _configure_pytest_mark(self):
        """ Mark test as skip. We won't create this ec2 instance """

        if "os_arch" in self.ec2_data and self.ec2_data["os_arch"] == "arm" and "buildpack" in self.weblog_name:
            logger.warn(f" WEBLOG: {self.weblog_name} doesn't support ARM architecture")
            return "missing_feature: Buildpack is not supported for ARM"
        # TODO Enable prod when we release
        if (
            self.env == "prod"
            and "os_arch" in self.ec2_data
            and self.ec2_data["os_arch"] == "arm"
            and "alpine" in self.weblog_name
        ):
            logger.warn(f"[bug][WEBLOG:  {self.weblog_name}] doesn't support ARM architecture")
            return "bug: Error loading shared library ld-linux-aarch64.so"

        return None

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
        from utils.onboarding.pulumi_utils import remote_install, pulumi_logger

        if self.pytestmark is not None:
            logger.warn(f"Skipping warmup for {self.name} due has mark {self.pytestmark}")
            return

        self.configure()
        logger.info(
            f"Launching VM.  With configuration is_uninstall: [{self.is_uninstall}], is_auto_install: {self.is_auto_install}, is_container: [{self.is_container}] "
        )
        # Startup VM and prepare connection
        self.ec2_server = aws.ec2.Instance(
            self.name,
            instance_type=self.ec2_data["instance_type"],
            vpc_security_group_ids=self.aws_infra_config.vpc_security_group_ids,
            subnet_id=self.aws_infra_config.subnet_id,
            key_name=PulumiSSH.keypair_name,
            ami=self.ec2_data["ami_id"] if self.ami_id is None else self.ami_id,
            tags={"Name": self.name,},
            opts=PulumiSSH.aws_key_resource,
        )

        pulumi.export("privateIp_" + self.name, self.ec2_server.private_ip)
        Output.all(self.ec2_server.private_ip).apply(lambda args: self.set_ip(args[0]))
        Output.all(self.ec2_server.private_ip, self.name).apply(
            lambda args: pulumi_logger(self.provision_scenario, "vms_desc").info(f"{args[0]}:{args[1]}")
        )

        self.ec2_server_connection = command.remote.ConnectionArgs(
            host=self.ec2_server.private_ip,
            user=self.ec2_data["user"],
            private_key=PulumiSSH.private_key_pem,
            dial_error_limit=-1,
        )

        # We apply initial configurations to the VM before starting with the installation proccess
        prepare_init_config_installer = remote_install(
            self.ec2_server_connection,
            "prepare_init_config_installer_" + self.name,
            self.prepare_init_config_install["install"],
            self.ec2_server,
            scenario_name=self.provision_scenario,
        )

        # To launch remote task in dependency order
        main_task_dep = prepare_init_config_installer

        if self.ami_id is None:
            # Ok. The AMI doesn't exist we should create.
            configure_repo_installer = self._configure_repositories_manual(prepare_init_config_installer)
            configure_docker_installer = self._configure_docker(configure_repo_installer)
            configure_lang_variant_installer = self._configure_lang_variant(configure_docker_installer)
            main_task_dep = self._create_AMI(configure_lang_variant_installer)
        else:
            logger.info("Using a previously existing AMI")

        agent_installer = self._agent_install(main_task_dep)
        autoinjection_installer = self._autoinjection_install(agent_installer)
        extract_components_installer = self._extract_installed_components(autoinjection_installer)
        run_weblog_installer = self.run_weblog(extract_components_installer)

        if self.is_uninstall:
            self._unistall_software_and_rerun_weblog(run_weblog_installer)

    def _configure_repositories_manual(self, task_dep):
        """ Launch commands to configure DD linux repositories (If we aren't using the installation script)"""
        if not self.is_auto_install:
            task_dep = remote_install(
                self.ec2_server_connection,
                "prepare-repos-installer_" + self.name,
                self.prepare_repos_install["install"],
                task_dep,
                scenario_name=self.provision_scenario,
            )
        return task_dep

    def _configure_docker(self, task_dep):
        """ Prepare docker installation if we are on container scenario """
        if self.is_container:
            task_dep = remote_install(
                self.ec2_server_connection,
                "prepare-docker-installer_" + self.name,
                self.prepare_docker_install["install"],
                task_dep,
                scenario_name=self.provision_scenario,
            )
        return task_dep

    def _configure_lang_variant(self, task_dep):
        """ Install language variants (not mandatory) """
        if "install" in self.language_variant_install_data:
            task_dep = remote_install(
                self.ec2_server_connection,
                "lang-variant-installer_" + self.name,
                self.language_variant_install_data["install"],
                task_dep,
                scenario_name=self.provision_scenario,
            )
        return task_dep

    def _create_AMI(self, task_dep):
        """ If the ami_name is None, we can not create the AMI (Probably because there another AMI is being generating) """
        import pulumi
        import pulumi_aws as aws

        if self.ami_name is not None:
            # Ok. All third party software is installed, let's create the ami to reuse it in the future
            logger.info(f"Creating AMI with name [{self.ami_name}] from instance ")
            # Expiration date for the ami
            # expiration_date = (datetime.now() + timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            task_dep = aws.ec2.AmiFromInstance(
                self.ami_name,
                # deprecation_time=expiration_date,
                source_instance_id=self.ec2_server.id,
                opts=pulumi.ResourceOptions(depends_on=[task_dep], retain_on_delete=True),
            )
        return task_dep

    def _agent_install(self, task_dep):
        """ Install agent. If we are using the autoinstall script, we also install the agent. The script we will use only for install autoinjection """
        return remote_install(
            self.ec2_server_connection,
            "agent-installer_" + self.name,
            self.agent_install_data,
            task_dep,
            scenario_name=self.provision_scenario,
            environment=self._get_command_environment(),
        )

    def _autoinjection_install(self, task_dep):
        """ Install autoinjection. The install_data can be for manual install or to use the script  """
        return remote_install(
            self.ec2_server_connection,
            "autoinjection-installer_" + self.name,
            self.autoinjection_install_data,
            task_dep,
            scenario_name=self.provision_scenario,
            environment=self._get_command_environment(),
        )

    def run_weblog(self, task_dep):
        """ Run the weblog app. The run command will depend on received task_dep """
        # Build weblog app
        return remote_install(
            self.ec2_server_connection,
            "run-weblog_" + self.name,
            self.weblog_install_data,
            task_dep,
            scenario_name=self.provision_scenario,
            environment=self._get_command_environment(),
        )

    def _unistall_software_and_rerun_weblog(self, task_dep):
        """ Uninstall process (stop app, uninstall autoinjection and rerun the app) """
        logger.info(f"Uninstall the autoinjection software. Command: {self.weblog_uninstall_data['uninstall']} ")
        weblog_uninstall = remote_install(
            self.ec2_server_connection,
            "uninstall-weblog_" + self.name,
            self.weblog_uninstall_data["uninstall"],
            task_dep,
            scenario_name=self.provision_scenario,
        )
        autoinjection_uninstall = remote_install(
            self.ec2_server_connection,
            "uninstall-autoinjection_" + self.name,
            self.autoinjection_uninstall_data[0],
            weblog_uninstall,
            scenario_name=self.provision_scenario,
        )
        # Rerun weblog app again, but without autoinstrumentation
        remote_install(
            self.ec2_server_connection,
            "rerun-weblog_" + self.name,
            self.weblog_install_data,
            autoinjection_uninstall,
            scenario_name=self.provision_scenario,
            environment=self._get_command_environment(),
        )

    def set_ip(self, instance_ip):
        self.ip = instance_ip

    def _extract_installed_components(self, task_dep):
        """ Extract installed component versions """
        return remote_install(
            self.ec2_server_connection,
            "installation-check_" + self.name,
            self.installation_check_data,
            task_dep,
            logger_name="pulumi_installed_versions",
            scenario_name=self.provision_scenario,
            output_callback=lambda command_output: self.set_components(command_output),
            environment=self._get_command_environment(),
        )

    def set_components(self, components_json):
        """Set installed software components version as json. ie {comp_name:version,comp_name2:version2...}"""
        self.components = json.loads(components_json.replace("'", '"'))

    def get_component(self, component_name):
        if component_name is None or self.components is None or not component_name in self.components:
            return Version("0.0.0", component_name)

        raw_version = self.components[component_name]
        # Workaround clean "Epoch" from debian packages.
        # The format is: [epoch:]upstream_version[-debian_revision]
        if ":" in raw_version:
            raw_version = raw_version.split(":")[1]

        if raw_version.strip() == "":
            return Version("0.0.0", component_name)
        return Version(raw_version.strip(), component_name)

    def _configure_ami(self):
        """ Check if there is an AMI for one test. Also check if we are using the env var to force the AMI creation"""
        import pulumi_aws as aws

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

    def _get_command_environment(self):
        command_env = {}
        for key, value in self.dd_config_distro.items():
            command_env["DD_" + key] = value
        # DD
        command_env["DD_API_KEY"] = self.datadog_config.dd_api_key
        command_env["DD_APP_KEY"] = self.datadog_config.dd_app_key
        # Docker
        command_env["DD_DOCKER_LOGIN"] = self.datadog_config.docker_login
        command_env["DD_DOCKER_LOGIN_PASS"] = self.datadog_config.docker_login_pass
        # Tested library
        command_env["DD_LANG"] = self.language if self.language != "nodejs" else "js"
        return command_env


## ^^^ The above code will be deleted when the migration is finished. ^^^


class AWSInfraConfig:
    def __init__(self) -> None:
        # Mandatory parameters
        self.subnet_id = os.getenv("ONBOARDING_AWS_INFRA_SUBNET_ID")
        self.vpc_security_group_ids = os.getenv("ONBOARDING_AWS_INFRA_SECURITY_GROUPS_ID", "").split(",")

        if None in (self.subnet_id, self.vpc_security_group_ids):
            logger.warn("AWS infastructure is not configured correctly for auto-injection testing")


class DataDogConfig:
    def __init__(self) -> None:
        self.dd_api_key = os.getenv("DD_API_KEY_ONBOARDING")
        self.dd_app_key = os.getenv("DD_APP_KEY_ONBOARDING")
        self.docker_login = os.getenv("DOCKER_LOGIN")
        self.docker_login_pass = os.getenv("DOCKER_LOGIN_PASS")

        if None in (self.dd_api_key, self.dd_app_key):
            logger.warn("Datadog agent is not configured correctly for auto-injection testing")


class _VagrantConfig:
    def __init__(self, box_name) -> None:
        self.box_name = box_name


class _AWSConfig:
    def __init__(self, ami_id, ami_instance_type, user) -> None:
        self.ami_id = ami_id
        self.ami_instance_type = ami_instance_type
        self.user = user
        self.aws_infra_config = AWSInfraConfig()


class _SSHConfig:
    def __init__(self, hostname=None, port=22, username=None, key_filename=None, pkey=None) -> None:
        self.hostname = hostname
        self.port = port
        self.username = username
        self.key_filename = key_filename
        self.pkey = pkey
        self.pkey_path = pkey

    def set_pkey(self, pkey):
        self.pkey = pkey

    def get_ssh_connection(self):
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if self.pkey_path is not None:
            if self.pkey is None:
                self.pkey = paramiko.RSAKey.from_private_key_file(self.pkey_path)
            ssh.connect(self.hostname, port=self.port, username=self.username, pkey=self.pkey)
        else:
            ssh.connect(self.hostname, port=self.port, username=self.username, key_filename=self.key_filename)
        return ssh


class _VirtualMachine:
    def __init__(self, name, aws_config, vagrant_config, os_type, os_distro, os_branch, os_cpu, **kwargs,) -> None:
        self.name = name
        self.datadog_config = DataDogConfig()
        self.aws_config = aws_config
        self.vagrant_config = vagrant_config
        self.ssh_config = _SSHConfig()
        self.os_type = os_type
        self.os_distro = os_distro
        self.os_branch = os_branch
        self.os_cpu = os_cpu
        self._vm_provision = None
        self.tested_components = {}
        self.deffault_open_port = 5985

    def set_ip(self, ip):
        self.ssh_config.hostname = ip

    def get_log_folder(self):
        vm_folder = f"{context.scenario.host_log_folder}/{self.name}"
        if not os.path.exists(vm_folder):
            os.mkdir(vm_folder)
        return vm_folder

    def get_default_log_file(self):
        return f"{self.get_log_folder()}/virtual_machine_{self.name}.log"

    def add_provision(self, provision):
        self._vm_provision = provision

    def get_provision(self):
        return self._vm_provision

    def set_tested_components(self, components_json):
        """Set installed software components version as json. ie {comp_name:version,comp_name2:version2...}"""
        self.tested_components = json.loads(components_json.replace("'", '"'))

    def get_cache_name(self):
        vm_cached_name = f"{self.name}_"
        if self.get_provision().lang_variant_installation:
            vm_cached_name += f"{self.get_provision().lang_variant_installation.id}_"
        for installation in self.get_provision().installations:
            if installation.cache:
                vm_cached_name += f"{installation.id}_"
        return vm_cached_name

    def get_command_environment(self):
        """ This environment will be injected as environment variables for all launched remote commands """
        command_env = {}
        for key, value in self.get_provision().env.items():
            command_env["DD_" + key] = value
        # DD
        if self.datadog_config.dd_api_key:
            command_env["DD_API_KEY"] = self.datadog_config.dd_api_key
        if self.datadog_config.dd_app_key:
            command_env["DD_APP_KEY"] = self.datadog_config.dd_app_key
        # Docker
        if self.datadog_config.docker_login:
            command_env["DD_DOCKER_LOGIN"] = self.datadog_config.docker_login
            command_env["DD_DOCKER_LOGIN_PASS"] = self.datadog_config.docker_login_pass
        # Tested library
        command_env["DD_LANG"] = command_env["DD_LANG"] if command_env["DD_LANG"] != "nodejs" else "js"
        # VM name
        command_env["DD_VM_NAME"] = self.name
        return command_env


class Ubuntu22amd64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "Ubuntu_22_amd64",
            aws_config=_AWSConfig(ami_id="ami-007855ac798b5175e", ami_instance_type="t2.medium", user="ubuntu"),
            vagrant_config=_VagrantConfig(box_name="bento/ubuntu-22.04"),
            os_type="linux",
            os_distro="deb",
            os_branch="ubuntu22_amd64",
            os_cpu="amd64",
            **kwargs,
        )


class Ubuntu22arm64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "Ubuntu_22_arm64",
            aws_config=_AWSConfig(ami_id="ami-016485166ec7fa705", ami_instance_type="t4g.small", user="ubuntu"),
            vagrant_config=_VagrantConfig(box_name="perk/ubuntu-2204-arm64",),
            os_type="linux",
            os_distro="deb",
            os_branch="ubuntu22_arm64",
            os_cpu="arm64",
            **kwargs,
        )


class Ubuntu18amd64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "Ubuntu_18_amd64",
            aws_config=_AWSConfig(ami_id="ami-0263e4deb427da90e", ami_instance_type="t2.medium", user="ubuntu"),
            # vagrant_config=_VagrantConfig(box_name="generic/ubuntu1804"),
            vagrant_config=None,
            os_type="linux",
            os_distro="deb",
            os_branch="ubuntu18_amd64",
            os_cpu="amd64",
            **kwargs,
        )


class AmazonLinux2amd64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "Amazon_Linux_2_amd64",
            aws_config=_AWSConfig(ami_id="ami-0dfcb1ef8550277af", ami_instance_type="t2.medium", user="ec2-user"),
            vagrant_config=_VagrantConfig(box_name="generic/centos7"),
            os_type="linux",
            os_distro="rpm",
            os_branch="amazon_linux2_amd64",
            os_cpu="amd64",
            **kwargs,
        )


class AmazonLinux2DotNet6(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "Amazon_Linux_2_DotNet6",
            aws_config=_AWSConfig(ami_id="ami-005b11f8b84489615", ami_instance_type="t2.medium", user="ec2-user"),
            vagrant_config=None,
            os_type="linux",
            os_distro="rpm",
            os_branch="amazon_linux2_dotnet6",
            os_cpu="amd64",
            **kwargs,
        )


class AmazonLinux2023amd64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "Amazon_Linux_2023_amd64",
            aws_config=_AWSConfig(ami_id="ami-06b09bfacae1453cb", ami_instance_type="t2.medium", user="ec2-user"),
            vagrant_config=_VagrantConfig(box_name="generic/centos9s"),
            os_type="linux",
            os_distro="rpm",
            os_branch="amazon_linux2023_amd64",
            os_cpu="amd64",
            **kwargs,
        )


class AmazonLinux2023arm64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "Amazon_Linux_2023_arm64",
            aws_config=_AWSConfig(ami_id="ami-04c97e62cb19d53f1", ami_instance_type="t4g.small", user="ec2-user"),
            # vagrant_config=_VagrantConfig(box_name="generic-a64/alma9"),
            vagrant_config=None,
            os_type="linux",
            os_distro="rpm",
            os_branch="amazon_linux2023_arm64",
            os_cpu="arm64",
            **kwargs,
        )
