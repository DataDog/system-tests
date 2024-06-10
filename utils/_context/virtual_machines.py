import os
import json
from utils.tools import logger

from utils._context.library_version import Version
from utils import context


class AWSInfraConfig:
    def __init__(self) -> None:
        # Mandatory parameters
        self.subnet_id = os.getenv("ONBOARDING_AWS_INFRA_SUBNET_ID")
        self.vpc_security_group_ids = os.getenv("ONBOARDING_AWS_INFRA_SECURITY_GROUPS_ID", "").split(",")
        self.iam_instance_profile = os.getenv("ONBOARDING_AWS_INFRA_IAM_INSTANCE_PROFILE")

        # if None in (self.subnet_id, self.vpc_security_group_ids):
        #    logger.warn("AWS infastructure is not configured correctly for auto-injection testing")


class DataDogConfig:
    def __init__(self) -> None:
        self.dd_api_key = os.getenv("DD_API_KEY_ONBOARDING")
        self.dd_app_key = os.getenv("DD_APP_KEY_ONBOARDING")
        self.docker_login = os.getenv("DOCKER_LOGIN")
        self.docker_login_pass = os.getenv("DOCKER_LOGIN_PASS")
        self.installer_versions = {}
        self.installer_versions["installer"] = os.getenv("DD_INSTALLER_INSTALLER_VERSION")
        self.installer_versions["library"] = os.getenv("DD_INSTALLER_LIBRARY_VERSION")
        self.installer_versions["agent"] = os.getenv("DD_INSTALLER_AGENT_VERSION")
        self.installer_versions["injector"] = os.getenv("DD_INSTALLER_INJECTOR_VERSION")

        # if None in (self.dd_api_key, self.dd_app_key):
        #    logger.warn("Datadog agent is not configured correctly for auto-injection testing")


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
        if self.datadog_config.installer_versions["installer"]:
            command_env["DD_INSTALLER_INSTALLER_VERSION"] = self.datadog_config.installer_versions["installer"]
        if self.datadog_config.installer_versions["agent"]:
            command_env["DD_INSTALLER_AGENT_VERSION"] = self.datadog_config.installer_versions["agent"]
        if self.datadog_config.installer_versions["library"]:
            command_env["DD_INSTALLER_LIBRARY_VERSION"] = self.datadog_config.installer_versions["library"]
        if self.datadog_config.installer_versions["injector"]:
            command_env["DD_INSTALLER_INJECTOR_VERSION"] = self.datadog_config.installer_versions["injector"]
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
            aws_config=_AWSConfig(ami_id="ami-064ed2d3fc01d3ec1", ami_instance_type="t2.medium", user="ec2-user"),
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
            aws_config=_AWSConfig(ami_id="ami-0a515c154e76934f7", ami_instance_type="t4g.small", user="ec2-user"),
            # vagrant_config=_VagrantConfig(box_name="generic-a64/alma9"),
            vagrant_config=None,
            os_type="linux",
            os_distro="rpm",
            os_branch="amazon_linux2023_arm64",
            os_cpu="arm64",
            **kwargs,
        )


class Centos7amd64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "CentOS_7_amd64",
            aws_config=_AWSConfig(ami_id="ami-002070d43b0a4f171", ami_instance_type="t2.medium", user="centos"),
            # vagrant_config=_VagrantConfig(box_name="generic-a64/alma9"),
            vagrant_config=None,
            os_type="linux",
            os_distro="rpm",
            os_branch="centos_7_amd64",
            os_cpu="amd64",
            **kwargs,
        )
