import os
import json
import hashlib

from utils.tools import logger
from utils._context.library_version import Version
from utils import context
from utils.onboarding.debug_vm import extract_logs_to_file


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


class _KrunVmConfig:
    def __init__(self, oci_image_name) -> None:
        self.oci_image_name = oci_image_name
        # KrunVm doesn't contain a good network capabilities. We use a std.in file to input parameters
        self.stdin = None


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
    def __init__(
        self,
        name,
        aws_config,
        vagrant_config,
        krunvm_config,
        os_type,
        os_distro,
        os_branch,
        os_cpu,
        default_vm=True,
        **kwargs,
    ) -> None:
        self.name = name
        self.datadog_config = DataDogConfig()
        self.aws_config = aws_config
        self.vagrant_config = vagrant_config
        self.krunvm_config = krunvm_config
        self.ssh_config = _SSHConfig()
        self.os_type = os_type
        self.os_distro = os_distro
        self.os_branch = os_branch
        self.os_cpu = os_cpu
        self._vm_provision = None
        self.tested_components = {}
        self.deffault_open_port = 5985
        self.agent_env = None
        self.app_env = None
        self.default_vm = default_vm

    def set_ip(self, ip):
        self.ssh_config.hostname = ip

    def get_ip(self):
        """ If we run the tests using xdist we lost the ip address of the VM. We can recover it from the logs"""
        if not self.ssh_config.hostname:
            self._load_ip_from_logs()
        return self.ssh_config.hostname

    def _load_ip_from_logs(self):
        """ Load the ip address from the logs"""
        vms_desc_file = f"{context.scenario.host_log_folder}/vms_desc.log"
        logger.info(f"Loading ip for {self.name} from {vms_desc_file}")
        if os.path.isfile(vms_desc_file):
            with open(vms_desc_file, "r") as f:
                for line in f:
                    if self.name in line:
                        self.ssh_config.hostname = line.split(":")[1]
                        logger.info(f"IP found for {self.name}. IP: {self.ssh_config.hostname}")
                        break

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

    def add_agent_env(self, agent_env):
        self.agent_env = agent_env

    def add_app_env(self, app_env):
        self.app_env = app_env

    def set_tested_components(self, components_json):
        """Set installed software components version as json. ie {comp_name:version,comp_name2:version2...}"""
        self.tested_components = json.loads(components_json.replace("'", '"'))

    def set_vm_logs(self, vm_logs):
        """ Extract /var/log/ files to a folder in the host machine """
        extract_logs_to_file(vm_logs, self.get_log_folder())

    def get_cache_name(self):
        vm_cached_name = f"{self.name}_"
        if self.get_provision().lang_variant_installation:
            vm_cached_name += f"{self.get_provision().lang_variant_installation.id}_"
        vm_cached_installations = ""
        for installation in self.get_provision().installations:
            if installation.cache:
                vm_cached_installations += f"{installation.id}_"
        vm_cached_installations = hashlib.shake_128(vm_cached_installations.encode("utf-8")).hexdigest(4)
        return vm_cached_name + vm_cached_installations

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
        # Scenario custom environment: agent and app env variables
        command_env["DD_AGENT_ENV"] = ""
        command_env["DD_APP_ENV"] = ""
        if self.agent_env:
            agent_env_values = ""
            for key, value in self.agent_env.items():
                agent_env_values += f"{key}={value} \r"
            command_env["DD_AGENT_ENV"] = agent_env_values
        if self.app_env:
            app_env_values = ""
            for key, value in self.app_env.items():
                app_env_values += f"{key}={value} "
            command_env["DD_APP_ENV"] = app_env_values
        else:
            # Containers are taking the generated file with this, and we need some value to be present to avoid failures like:
            # failed to read /home/ubuntu/scenario_app.env: line 1: unexpected character "'" in variable name "''"
            command_env["DD_APP_ENV"] = "foo=bar"

        return command_env


class Ubuntu22amd64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "Ubuntu_22_amd64",
            aws_config=_AWSConfig(ami_id="ami-007855ac798b5175e", ami_instance_type="t2.medium", user="ubuntu"),
            vagrant_config=_VagrantConfig(box_name="bento/ubuntu-22.04"),
            krunvm_config=None,
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
            krunvm_config=_KrunVmConfig(oci_image_name="docker.io/library/ubuntu_datadog:22"),
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
            krunvm_config=None,
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
            krunvm_config=None,
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
            krunvm_config=None,
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
            krunvm_config=None,
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
            krunvm_config=_KrunVmConfig(oci_image_name="docker.io/library/amazonlinux_datadog:2023"),
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
            krunvm_config=None,
            os_type="linux",
            os_distro="rpm",
            os_branch="centos_7_amd64",
            os_cpu="amd64",
            default_vm=False,
            **kwargs,
        )


# Oracle Linux 9.2. Owner oracle, id: 131827586825
class OracleLinux92amd64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "OracleLinux_9_2_amd64",
            aws_config=_AWSConfig(ami_id="ami-01453ca80e53609e3", ami_instance_type="t2.medium", user="ec2-user"),
            vagrant_config=None,
            krunvm_config=None,
            os_type="linux",
            os_distro="rpm",
            os_branch="oracle_linux",
            os_cpu="amd64",
            default_vm=False,
            **kwargs,
        )


class OracleLinux92arm64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "OracleLinux_9_2_arm64",
            aws_config=_AWSConfig(ami_id="ami-0d1bcd0124ba74024", ami_instance_type="t4g.small", user="ec2-user"),
            vagrant_config=None,
            krunvm_config=None,
            os_type="linux",
            os_distro="rpm",
            os_branch="oracle_linux",
            os_cpu="arm64",
            default_vm=False,
            **kwargs,
        )


# Oracle Linux 8.8. Owner oracle, id: 131827586825
class OracleLinux88amd64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "OracleLinux_8_8_amd64",
            aws_config=_AWSConfig(ami_id="ami-02a7419f257858fad", ami_instance_type="t2.medium", user="ec2-user"),
            vagrant_config=None,
            krunvm_config=None,
            os_type="linux",
            os_distro="rpm",
            os_branch="oracle_linux",
            os_cpu="amd64",
            default_vm=False,
            **kwargs,
        )


class OracleLinux88arm64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "OracleLinux_8_8_arm64",
            aws_config=_AWSConfig(ami_id="ami-0463a0d7ecd42cc89", ami_instance_type="t4g.small", user="ec2-user"),
            vagrant_config=None,
            krunvm_config=None,
            os_type="linux",
            os_distro="rpm",
            os_branch="oracle_linux",
            os_cpu="arm64",
            default_vm=False,
            **kwargs,
        )


# Oracle Linux 7.9. Owner oracle, id: 131827586825
class OracleLinux79amd64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "OracleLinux_7_9_amd64",
            aws_config=_AWSConfig(ami_id="ami-0fb08d5eb039a9ebd", ami_instance_type="t2.medium", user="ec2-user"),
            vagrant_config=None,
            krunvm_config=None,
            os_type="linux",
            os_distro="rpm",
            os_branch="oracle_linux",
            os_cpu="amd64",
            default_vm=False,
            **kwargs,
        )


class Debian12amd64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "Debian_12_amd64",
            aws_config=_AWSConfig(ami_id="ami-064519b8c76274859", ami_instance_type="t2.medium", user="ubuntu"),
            vagrant_config=None,
            krunvm_config=None,
            os_type="linux",
            os_distro="deb",
            os_branch="debian12_amd64",
            os_cpu="amd64",
            **kwargs,
        )


class Debian12arm64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "Debian_12_arm64",
            aws_config=_AWSConfig(ami_id="ami-0789039e34e739d67", ami_instance_type="t2.medium", user="ubuntu"),
            vagrant_config=None,
            krunvm_config=None,
            os_type="linux",
            os_distro="deb",
            os_branch="debian12_arm64",
            os_cpu="arm64",
            **kwargs,
        )
