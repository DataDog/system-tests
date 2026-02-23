from copy import copy
import os
import json
import hashlib

from utils.virtual_machine.virtual_machine_provisioner import Provision, _DeployedWeblog


class AWSInfraConfig:
    def __init__(self) -> None:
        # Mandatory parameters
        self.subnet_id = os.getenv("ONBOARDING_AWS_INFRA_SUBNET_ID", "").split(",")
        self.vpc_security_group_ids = os.getenv("ONBOARDING_AWS_INFRA_SECURITY_GROUPS_ID", "").split(",")
        self.iam_instance_profile = os.getenv("ONBOARDING_AWS_INFRA_IAM_INSTANCE_PROFILE")


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

        # Cached properties
        self.skip_cache = os.getenv("SKIP_AMI_CACHE", "False").lower() == "true"
        self.update_cache = os.getenv("AMI_UPDATE", "False").lower() == "true"


class _VagrantConfig:
    def __init__(self, box_name: str) -> None:
        self.box_name = box_name


class _KrunVmConfig:
    stdin: str | None

    def __init__(self, oci_image_name: str) -> None:
        self.oci_image_name = oci_image_name
        # KrunVm doesn't contain a good network capabilities. We use a std.in file to input parameters
        self.stdin = None


class _AWSConfig:
    def __init__(self, ami_id: str, ami_instance_type: str, user: str, volume_size: int = 20) -> None:
        self.ami_id = ami_id
        self.ami_instance_type = ami_instance_type
        self.user = user
        self.aws_infra_config = AWSInfraConfig()
        self.volume_size = volume_size


class _SSHConfig:
    def __init__(
        self,
        hostname: str | None = None,
        port: int = 22,
        username: str | None = None,
        key_filename: str | None = None,
        pkey: str | None = None,
    ) -> None:
        self.hostname = hostname
        self.port = port
        self.username = username
        self.key_filename = key_filename
        self.pkey = pkey
        self.pkey_path = pkey

    def set_pkey(self, pkey: str):
        self.pkey = pkey

    def get_ssh_connection(self):
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507
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
        name: str,
        aws_config: _AWSConfig,
        vagrant_config: _VagrantConfig,
        krunvm_config: _KrunVmConfig,
        os_type: str,
        os_distro: str,
        os_branch: str,
        os_cpu: str,
        *,
        default_vm: bool = True,
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
        self._vm_provision: Provision | None = None
        self.tested_components = {}
        self.deffault_open_port: int = 5985
        self.agent_env: dict[str, str] | None = None
        self.app_env: dict[str, str] | None = None
        self.default_vm: bool = default_vm
        self._deployed_weblog: _DeployedWeblog | None = None
        self.provision_install_error = None

    def get_deployed_weblog(self):
        self._check_provsion_install_error()
        if self._deployed_weblog is None:
            self._deployed_weblog = self._vm_provision.get_deployed_weblog()

        return self._deployed_weblog

    def set_deployed_weblog(self, deployed_weblog: _DeployedWeblog):
        self._deployed_weblog = deployed_weblog

    def get_vm_unique_id(self):
        return f"{self.name}_{self.get_deployed_weblog().runtime_version}_{self.get_deployed_weblog().app_type}"

    def set_ip(self, ip: str):
        self.ssh_config.hostname = ip

    def get_ssh_connection(self):
        self._check_provsion_install_error()
        return self.ssh_config.get_ssh_connection()

    def get_ip(self):
        self._check_provsion_install_error()
        if not self.ssh_config.hostname:
            raise Exception("IP not found")
        return self.ssh_config.hostname

    def _check_provsion_install_error(self):
        assert self.provision_install_error is None, (
            f"❌ There are previous errors in the virtual machine provisioning steps. "
            f"Check this file in the logs scenario folder: {self.name}.log"
        )

    def add_provision(self, provision: Provision) -> None:
        self._vm_provision = provision

    def get_provision(self) -> Provision:
        return self._vm_provision

    def add_agent_env(self, agent_env: dict[str, str]):
        self.agent_env = agent_env

    def add_app_env(self, app_env: dict[str, str]):
        self.app_env = app_env

    def set_tested_components(self, components_json: str):
        """Set installed software components version as json. ie {comp_name:version,comp_name2:version2...}"""
        self.tested_components = json.loads(components_json.replace("'", '"'))

    def get_cache_name(self):
        """Generate a unique name for the  cache.
        use: vm name + provision name + weblog id + hash of the cacheable installations
        We geneate the hash from cacheable steps content. If we modify the step scripts
        the hash will change and the cache will be regenerated.
        If we use the AWS provider: The AWS AMI is limited to 128 characters, so we need to keep the name short
        """
        # Cache prefix (no encoded)
        cached_name = (
            f"{self.name}_{self.get_provision().provision_name}_{self.get_provision().weblog_installation.id}_"
        )
        # Cache suffix. All cacheable steps encoded
        vm_cached_name = ""
        if self.get_provision().lang_variant_installation:
            vm_cached_name += f"{self.get_provision().lang_variant_installation}_"
        for installation in self.get_provision().installations:
            if installation.cache:
                vm_cached_name += f"{installation}_"

        full_cache_name = cached_name + hashlib.md5(vm_cached_name.encode("utf-8")).hexdigest()

        if len(full_cache_name) >= 120:
            # There is a limit of 128 characters for the AMI name. 119 + 9 characters added by the aws
            # for now encoding provision_name is enough to keep the name short
            provision_name = hashlib.shake_128(self.get_provision().provision_name.encode("utf-8")).hexdigest(4)
            cached_name = f"{self.name}_{provision_name}_{self.get_provision().weblog_installation.id}_"
            full_cache_name = cached_name + hashlib.md5(vm_cached_name.encode("utf-8")).hexdigest()
        return full_cache_name

    def get_command_environment(self) -> dict[str, str]:
        """Get the environment that will be injected as environment variables for all launched remote commands"""
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
                agent_env_values += f"{key}={value}\n"
            command_env["DD_AGENT_ENV"] = agent_env_values
        if self.app_env:
            app_env_values = ""
            for key, value in self.app_env.items():
                app_env_values += f"{key}={value} "
            command_env["DD_APP_ENV"] = app_env_values
        else:
            # Containers are taking the generated file with this, and we need some value to be present to avoid
            # failures like:
            # failed to read /home/ubuntu/scenario_app.env: line 1: unexpected character "'" in variable name "''"
            command_env["DD_APP_ENV"] = "foo=bar"

        return command_env

    def get_tested_apps_vms(self):
        """Workaround for multicontainer apps. We are going duplicate the machines for each runtime inside of docker
        compose. This means, if I have a multicontainer app with 3 containers (runtimes) running on 1 vm, I will have 3
        machines with the same configuration but with different runtimes.
        NOTE: On AWS we only run 1 vm. We duplicate the vms for test isolation.
        """
        vms_by_runtime = []
        vms_by_runtime_ids = []
        deployed_weblog = self.get_provision().get_deployed_weblog()
        if deployed_weblog.app_type == "multicontainer":
            for weblog in deployed_weblog.multicontainer_apps:
                vm_by_runtime = copy(self)
                vm_by_runtime.set_deployed_weblog(weblog)
                vms_by_runtime.append(vm_by_runtime)
                vms_by_runtime_ids.append(vm_by_runtime.get_vm_unique_id())
        else:
            vms_by_runtime.append(self)
            vms_by_runtime_ids.append(self.get_vm_unique_id())

        return vms_by_runtime, vms_by_runtime_ids


def load_virtual_machines(provider_id: str):
    with open("utils/virtual_machine/virtual_machines.json", "r") as file:
        data = json.load(file)

    vm_objects = []
    for vm_data in data["virtual_machines"]:
        if (
            (provider_id == "vagrant" and vm_data["vagrant_config"] is not None)
            or (provider_id == "krunvm" and vm_data["krunvm_config"] is not None)
            or (provider_id == "aws" and vm_data["aws_config"] is not None)
        ):
            aws_config = None
            vagrant_config = None
            krunvm_config = None

            if vm_data["aws_config"] is not None:
                aws_config = _AWSConfig(
                    ami_id=vm_data["aws_config"]["ami_id"],
                    ami_instance_type=vm_data["aws_config"]["ami_instance_type"],
                    user=vm_data["aws_config"]["user"],
                    volume_size=vm_data["aws_config"].get("volume_size", 20),
                )
            if "vagrant_config" in vm_data and vm_data["vagrant_config"] is not None:
                vagrant_config = _VagrantConfig(box_name=vm_data["vagrant_config"]["box_name"])
            if "krunvm_config" in vm_data and vm_data["krunvm_config"] is not None:
                krunvm_config = _KrunVmConfig(oci_image_name=vm_data["krunvm_config"]["oci_image_name"])

            vm = _VirtualMachine(
                name=vm_data["name"],
                aws_config=aws_config,
                vagrant_config=vagrant_config,
                krunvm_config=krunvm_config,
                os_type=vm_data["os_type"],
                os_distro=vm_data["os_distro"],
                os_branch=vm_data["os_branch"],
                os_cpu=vm_data["os_cpu"],
                default_vm=vm_data["default_vm"],
            )
            if "disabled" not in vm_data or vm_data["disabled"] != "true":
                vm_objects.append(vm)

    return vm_objects
