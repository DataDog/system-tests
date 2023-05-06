from tests.onboarding.utils.provision_parser import Provision_parser, Provision_filter
from utils._context.virtual_machines import TestedVirtualMachine


class ProvisionMatrix:
    def __init__(self, provision_filter):
        self.provision_filter = provision_filter
        self.provision_parser = Provision_parser(provision_filter)

    def get_infraestructure_provision(self):
        for ec2_data in self.provision_parser.ec2_instances_data():
            os_type = ec2_data["os_type"]
            os_distro = ec2_data["os_distro"]
            os_branch = ec2_data.get("os_branch", None)

            # for every different agent instalation
            for agent_instalations in self.provision_parser.ec2_agent_install_data(os_type, os_distro, os_branch):
                # for every different autoinjection software (by language, by os and by env)
                for autoinjection_instalations in self.provision_parser.ec2_autoinjection_install_data(
                    os_type, os_distro, os_branch
                ):
                    language = autoinjection_instalations["language"]
                    # for every different language variants. If the aren't language_variants for this language
                    # the function "ec2_language_variants_install_data" will return an array with an empty dict
                    for language_variants_instalations in self.provision_parser.ec2_language_variants_install_data(
                        language, os_type, os_distro, os_branch
                    ):
                        # for every weblog supported for every language variant or weblog variant without "supported-language-versions"
                        for weblog_instalations in self.provision_parser.ec2_weblogs_install_data(
                            language, language_variants_instalations["version"], os_type, os_distro, os_branch
                        ):
                            yield TestedVirtualMachine(
                                ec2_data,
                                agent_instalations,
                                language,
                                autoinjection_instalations,
                                language_variants_instalations,
                                weblog_instalations,
                                self.provision_filter,
                            )
