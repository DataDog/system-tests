import yaml
from yaml.loader import SafeLoader
from yamlinclude import YamlIncludeConstructor
import os
from utils.tools import logger
from utils._context.virtual_machines import TestedVirtualMachine


class ProvisionMatrix:
    def __init__(self, provision_filter):
        self.provision_filter = provision_filter
        self.provision_parser = Provision_parser(provision_filter)

    def get_infraestructure_provision(self):
        for ec2_data in self.provision_parser.ec2_instances_data():
            # for every different agent instalation
            for agent_instalations in self.provision_parser.ec2_agent_install_data():
                # for every different autoinjection software (by language, by os and by env)
                for autoinjection_instalations in self.provision_parser.ec2_autoinjection_install_data():
                    # for every different language variants. If the aren't language_variants for this language
                    # the function "ec2_language_variants_install_data" will return an array with an empty dict
                    for language_variants_instalations in self.provision_parser.ec2_language_variants_install_data():
                        # for every weblog supported for every language variant or weblog variant without "supported-language-versions"
                        for weblog_instalations in self.provision_parser.ec2_weblogs_install_data(
                            language_variants_instalations["version"]
                        ):
                            prepare_repos_install = self.provision_parser.ec2_prepare_repos_install_data()
                            prepare_docker_install = self.provision_parser.ec2_prepare_docker_install_data()
                            installation_check_data = self.provision_parser.ec2_installation_checks_data()
                            yield TestedVirtualMachine(
                                ec2_data,
                                agent_instalations,
                                self.provision_filter.language,
                                autoinjection_instalations,
                                language_variants_instalations,
                                weblog_instalations,
                                prepare_repos_install,
                                prepare_docker_install,
                                installation_check_data,
                            )


class Provision_parser:
    def __init__(self, provision_filter):
        self.provision_filter = provision_filter
        self.config_data = self._load_provision()

    def ec2_instances_data(self):
        for ami_data in self.config_data["ami"]:
            os_distro_filter = os.getenv("ONBOARDING_FILTER_OS_DISTRO")
            if os_distro_filter and ami_data["os_distro"] != os_distro_filter:
                continue
            self._set_ami_filter(ami_data)
            yield ami_data

    def _set_ami_filter(self, ami_data):
        # Update filter with ami specs
        self.provision_filter.os_type = ami_data["os_type"]
        self.provision_filter.os_distro = ami_data["os_distro"]
        self.provision_filter.os_branch = ami_data.get("os_branch", None)

    def ec2_agent_install_data(self):
        for agent_data in self._filter_provision_data(self.config_data, "agent"):
            yield agent_data

    def ec2_autoinjection_install_data(self):
        autoinjection_language_data = self._get_autoinjection_data_for_current_lang()
        for autoinjection_env_data in autoinjection_language_data:
            if self.provision_filter.env and autoinjection_env_data["env"] != self.provision_filter.env:
                continue
            filteredInstalations = self._filter_install_data(autoinjection_env_data)
            # No instalation for this os_type/branch. Skip it
            if not filteredInstalations:
                continue

            yield {"env": autoinjection_env_data["env"], "install": filteredInstalations[0]}

    def _get_autoinjection_data_for_current_lang(self):
        for autoinjection_language_data in self.config_data["autoinjection"]:
            if self.provision_filter.language in autoinjection_language_data:
                return autoinjection_language_data[self.provision_filter.language]

    def ec2_language_variants_install_data(self):
        language_variants_data_result = []

        # Language variants are not mandatory. Perhaps the yml file doesn't contain this node
        if "language-variants" in self.config_data:
            for language_variants_data in self.config_data["language-variants"]:
                for filtered_language_variants_data in self._filter_provision_data(
                    language_variants_data, self.provision_filter.language
                ):
                    language_variants_data_result.append(filtered_language_variants_data)

        # If the aren't language variants for this language, we allways return one row.
        # This let us to search weblog variants without "language_specification" versionn (ie container based apps)
        if not language_variants_data_result:
            language_variants_data_result.append(dict(version=None, name="None"))

        return language_variants_data_result

    def ec2_prepare_repos_install_data(self):
        filteredInstalations = self._filter_install_data(self.config_data["prepare-repos"], exact_match=False)
        return dict(install=filteredInstalations[0])

    def ec2_prepare_docker_install_data(self):
        if "prepare-docker" not in self.config_data:
            return dict(install=None)
        filteredInstalations = self._filter_install_data(self.config_data["prepare-docker"], exact_match=False)
        return dict(install=filteredInstalations[0])

    def ec2_weblogs_install_data(self, support_version):
        for language_weblog_data in self.config_data["weblogs"]:
            for filtered_weblog_data in self._filter_provision_data(
                language_weblog_data, self.provision_filter.language, exact_match=True
            ):
                if (not support_version and "supported-language-versions" not in filtered_weblog_data) or (
                    support_version in filtered_weblog_data["supported-language-versions"]
                ):
                    weblog_filter = self.provision_filter.weblog
                    if weblog_filter and filtered_weblog_data["name"] != weblog_filter:
                        continue
                    yield filtered_weblog_data

    def ec2_installation_checks_data(self):
        for installation_checks_data in self.config_data["installation_checks"]:
            for filtered_installation_checks_data in self._filter_provision_data(
                installation_checks_data, self.provision_filter.language
            ):
                # Only one check
                return filtered_installation_checks_data

    def _filter_install_data(self, data, exact_match=False):

        os_type = self.provision_filter.os_type
        os_distro = self.provision_filter.os_distro
        os_branch = self.provision_filter.os_branch
        # Filter by type,  distro and branch
        filteredInstalations = [
            agent_data_install
            for agent_data_install in data["install"]
            if agent_data_install["os_type"] == os_type
            and ("os_distro" in agent_data_install and agent_data_install["os_distro"] == os_distro)
            and ("os_branch" in agent_data_install and agent_data_install["os_branch"] == os_branch)
        ]

        # Weblog is exact_match=true. If AMI has os_branch we will execute only weblogs with the same os_branch
        # If weblog has os_branch, we will execute this weblog only in machines with os_branch
        if exact_match is True:
            if os_branch is not None:
                return filteredInstalations
            elif os_branch is None:
                filteredInstalations = [
                    agent_data_install for agent_data_install in data["install"] if "os_branch" in agent_data_install
                ]
                if filteredInstalations:
                    return []

        # Filter by type and distro
        if not filteredInstalations:
            filteredInstalations = [
                agent_data_install
                for agent_data_install in data["install"]
                if agent_data_install["os_type"] == os_type
                and ("os_distro" in agent_data_install and agent_data_install["os_distro"] == os_distro)
            ]

        # Filter by type
        if not filteredInstalations:
            filteredInstalations = [
                agent_data_install
                for agent_data_install in data["install"]
                if agent_data_install["os_type"] == os_type and "os_distro" not in agent_data_install
            ]

        # Only one instalation
        if len(filteredInstalations) > 1:
            raise Exception("Only one type of installation is allowed!", os_type, os_distro)

        return filteredInstalations

    def _filter_provision_data(self, data, node_name, exact_match=False):
        filtered_data = []
        if node_name in data:
            for provision_data in data[node_name]:

                filteredInstalations = self._filter_install_data(provision_data, exact_match)

                # No instalation for this os_type/branch. Skip it
                if not filteredInstalations:
                    continue

                allowed_fields = ["env", "version", "name", "supported-language-versions"]
                dic_data = {}
                dic_data["install"] = filteredInstalations[0]
                for allowed_field in allowed_fields:
                    if allowed_field in provision_data:
                        dic_data[allowed_field] = provision_data[allowed_field]
                filtered_data.append(dic_data)

        return filtered_data

    def _load_provision(self):
        YamlIncludeConstructor.add_to_loader_class(loader_class=yaml.FullLoader, base_dir=".")
        self.provision_filter.provision_scenario
        # Open the file and load the file
        provision_file = (
            "tests/onboarding/infra_provision/provision_" + self.provision_filter.provision_scenario.lower() + ".yml"
        )
        with open(provision_file) as f:
            config_data = yaml.load(f, Loader=yaml.FullLoader)
        return config_data


class Provision_filter:
    def __init__(self, provision_scenario, language=None, env=None, os_distro=None, weblog=None):
        self.provision_scenario = provision_scenario
        self.language = os.getenv("TEST_LIBRARY")
        if self.language is None:
            raise ValueError("You must set TEST_LIBRARY env variable!!")
        self.env = os.getenv("ONBOARDING_FILTER_ENV")
        self.os_distro = os.getenv("ONBOARDING_FILTER_OS_DISTRO")
        self.weblog = os.getenv("ONBOARDING_FILTER_WEBLOG")
