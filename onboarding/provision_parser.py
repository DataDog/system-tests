import yaml
from yaml.loader import SafeLoader
from yamlinclude import YamlIncludeConstructor


class Provision_parser:
    def __init__(self, provision_filter):
        self.provision_filter = provision_filter

    def ec2_instances_data(self):
        config_data = self._load_provision()
        for ami_data in config_data["ami"]:
            os_distro_filter = self.provision_filter.os_distro
            if os_distro_filter and ami_data["os_distro"] != os_distro_filter:
                continue
            yield ami_data

    def ec2_agent_install_data(self, os_type, os_distro, os_branch):
        config_data = self._load_provision()
        for agent_data in self._filter_provision_data(config_data, "agent", os_type, os_distro, os_branch):
            yield agent_data

    def ec2_autoinjection_install_data(self, os_type, os_distro, os_branch):
        config_data = self._load_provision()
        for autoinjection_data in config_data["autoinjection"]:
            for autoinjection_language_data in autoinjection_data:
                for autoinjection_env_data in self._filter_provision_data(
                    autoinjection_data, autoinjection_language_data, os_type, os_distro, os_branch
                ):
                    env_filter = self.provision_filter.env
                    if env_filter and autoinjection_env_data["env"] != env_filter:
                        continue

                    autoinjection_env_data["language"] = autoinjection_language_data
                    language_filter = self.provision_filter.language
                    if language_filter and autoinjection_env_data["language"] != language_filter:
                        continue
                    yield autoinjection_env_data

    def ec2_language_variants_install_data(self, language, os_type, os_distro, os_branch):
        config_data = self._load_provision()
        for language_variants_data in config_data["language-variants"]:
            for filtered_language_variants_data in self._filter_provision_data(
                language_variants_data, language, os_type, os_distro, os_branch
            ):
                yield filtered_language_variants_data

    def ec2_prepare_repos_install_data(self, os_type, os_distro):
        config_data = self._load_provision()
        filteredInstalations = self._filter_install_data(
            config_data["prepare-repos"], os_type, os_distro, os_branch=None, exact_match=False
        )
        config_data["prepare-repos"]["install"] = filteredInstalations[0]
        return config_data["prepare-repos"]

    def ec2_weblogs_install_data(self, language, support_version, os_type, os_distro, os_branch):
        config_data = self._load_provision()
        for language_weblog_data in config_data["weblogs"]:
            for filtered_weblog_data in self._filter_provision_data(
                language_weblog_data, language, os_type, os_distro, os_branch, exact_match=True
            ):
                if support_version in filtered_weblog_data["supported-language-versions"]:
                    weblog_filter = self.provision_filter.weblog
                    if weblog_filter and filtered_weblog_data["name"] != weblog_filter:
                        continue
                    yield filtered_weblog_data

    def _filter_install_data(self, data, os_type, os_distro, os_branch, exact_match=False):
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

    def _filter_provision_data(self, config_data, node_name, os_type, os_distro, os_branch, exact_match=False):
        filtered_data = []
        if node_name in config_data:
            for provision_data in config_data[node_name]:
                filteredInstalations = self._filter_install_data(
                    provision_data, os_type, os_distro, os_branch, exact_match
                )
                # No agent instalation for this os_type/branch. Skip it
                if not filteredInstalations:
                    continue
                provision_data["install"] = filteredInstalations[0]
                filtered_data.append(provision_data)
        return filtered_data

    def _load_provision(self):
        YamlIncludeConstructor.add_to_loader_class(loader_class=yaml.FullLoader, base_dir=".")
        # Open the file and load the file
        provision_file = "provision_" + self.provision_filter.provision_scenario + ".yml"
        with open(provision_file) as f:
            config_data = yaml.load(f, Loader=yaml.FullLoader)
        return config_data
