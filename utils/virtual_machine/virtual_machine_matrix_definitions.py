# from utils._context.virtual_machines import SupportedVirtualMachines


try:
    from utils.virtual_machine.virtual_machines import SupportedVirtualMachines
except ImportError:
    from virtual_machines import SupportedVirtualMachines


class VMWeblogDescriptor:
    """Encapsulates information of the weblog: name, library and
    supported vm
    """

    def __init__(self, name, library, supported_vms):
        self.name = name
        self.library = library
        self.supported_vms = supported_vms


# NODEJS WEBLOGS
TEST_APP_NODEJS = VMWeblogDescriptor(
    "test-app-nodejs",
    "nodejs",
    SupportedVirtualMachines().excluded_os_branches(
        [
            "ubuntu22_amd64",
            "ubuntu22_arm64",
            "ubuntu21",
            "ubuntu20_arm64",
            "ubuntu20_amd64",
            "centos_7_amd64",
            "rhel_7_amd64",
            "amazon_linux2",
        ]
    ),
)
TEST_APP_NODEJS_08 = VMWeblogDescriptor(
    "test-app-nodejs-08",
    "nodejs",
    SupportedVirtualMachines().exact_os_branches(["ubuntu20_amd64", "centos_7_amd64"]),
)

TEST_APP_NODEJS_16 = VMWeblogDescriptor(
    "test-app-nodejs-16",
    "nodejs",
    SupportedVirtualMachines().excluded_os_branches(
        [
            "centos_7_amd64",
        ]
    ),
)

TEST_APP_NODEJS_ALPINE = VMWeblogDescriptor(
    "test-app-nodejs-alpine", "nodejs", SupportedVirtualMachines().get_all_virtual_machines()
)

TEST_APP_NODEJS_CONTAINER = VMWeblogDescriptor(
    "test-app-nodejs-container", "nodejs", SupportedVirtualMachines().get_all_virtual_machines()
)
TEST_APP_NODEJS_ESM = VMWeblogDescriptor(
    "test-app-nodejs-esm",
    "nodejs",
    SupportedVirtualMachines().exact_os_branches(["ubuntu24"]),
)
TEST_APP_NODEJS_MULTICONTAINER = VMWeblogDescriptor(
    "test-app-nodejs-multicontainer",
    "nodejs",
    SupportedVirtualMachines().exact_os_branches(["ubuntu24"]),
)
TEST_APP_NODEJS_UNSUPPORTED_DEFAULTS = VMWeblogDescriptor(
    "test-app-nodejs-unsupported-defaults",
    "nodejs",
    SupportedVirtualMachines().exact_os_branches(
        ["ubuntu22_amd64", "ubuntu22_arm64", "ubuntu21", "ubuntu20_arm64", "ubuntu20_amd64", "centos_7_amd64"]
    ),
)

# HERE ADD YOUR WEBLOG DEFINITION TO THE LIST
ALL_WEBLOGS = [
    TEST_APP_NODEJS,
    TEST_APP_NODEJS_08,
    TEST_APP_NODEJS_16,
    TEST_APP_NODEJS_ALPINE,
    TEST_APP_NODEJS_CONTAINER,
    TEST_APP_NODEJS_ESM,
    TEST_APP_NODEJS_MULTICONTAINER,
    TEST_APP_NODEJS_UNSUPPORTED_DEFAULTS,
]


def check_weblog_can_run_on_vm(lang, weblog_name, vm_name):
    """Check if the weblog variant is supported"""
    for weblog in ALL_WEBLOGS:
        if weblog_name == weblog.name:
            if lang == weblog.library:
                for supported_vm in weblog.supported_vms:
                    if supported_vm.name == vm_name:
                        return
            raise ValueError(
                f"Weblog variant {weblog_name} is not supported for {vm_name} (please check virtual_machine_definitions.py)"
            )


def get_supported_vms(lang, weblog_name, provider_id, default_vms="True", scenario_vms_exclude=None):
    """Get the supported vms for a weblog variant"""
    if scenario_vms_exclude is None:
        scenario_vms_exclude = []
    for weblog in ALL_WEBLOGS:
        if weblog_name == weblog.name and lang == weblog.library:
            supported_vms = weblog.supported_vms
            # Filter the vms that are not in the scenario_vms_exclude list and that are supported by the provider
            filtered_vms = [
                vm
                for vm in supported_vms
                if (vm.name not in scenario_vms_exclude and provider_id == "vagrant" and vm.vagrant_config is not None)
                or (provider_id == "krunvm" and vm.krunvm_config is not None)
                or (provider_id == "aws" and vm.aws_config is not None)
            ]
            if default_vms == "All":
                return filtered_vms
            elif default_vms == "True":
                return [vm for vm in filtered_vms if vm.default_vm]
            elif default_vms == "False":
                return [vm for vm in filtered_vms if not vm.default_vm]
            else:
                raise ValueError(f"Invalid value for default_vms: {default_vms}")

    raise ValueError(f"Weblog variant {weblog_name} not found (please check virtual_machine_definitions.py)")


if __name__ == "__main__":
    vms = get_supported_vms("nodejs", "test-app-nodejs")
    print(vms)  # noqa: T201
