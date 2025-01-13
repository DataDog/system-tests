from .auto_injection import _VirtualMachineScenario

class NewAutoInjectionScenario(_VirtualMachineScenario):

    def __init__(
        self,
        name,
        doc,
        vm_provision="new-installer-auto-inject", #Reference to the provision for this scenario
        agent_env=None,
        app_env=None,
        scenario_groups=None,
        github_workflow=None,
    ) -> None:
        # Specific configuration for the weblogs deployed using this scenario
        app_env_defaults = {
            "DD_TRACE_RATE_LIMIT": "1000000000000",
            "DD_TRACE_SAMPLING_RULES": "'[{\"sample_rate\":1}]'",
        }
        if app_env is not None:
            app_env_defaults.update(app_env)

        super().__init__(
            name,
            vm_provision=vm_provision,
            agent_env=agent_env,
            app_env=app_env_defaults,
            doc=doc,
            github_workflow=github_workflow,
            include_ubuntu_22_amd64=True,
            include_ubuntu_22_arm64=True,
            include_amazon_linux_2_amd64=True,
            include_amazon_linux_2_arm64=True,
            include_amazon_linux_2023_amd64=True,
            include_amazon_linux_2023_arm64=True,
            include_redhat_7_9_amd64=True,
            include_redhat_8_amd64=True,
            include_redhat_8_arm64=True,
            include_redhat_9_amd64=True,
            include_redhat_9_arm64=True,
            scenario_groups=scenario_groups,
        )
