import yaml
from yaml.loader import SafeLoader


def ec2_instances_data():
    config_data = _load_provision()
    for ami_data in config_data["ami"]:
        yield ami_data


def ec2_agent_install_data(os_type, os_branch=None):
    config_data = _load_provision()
    for agent_data in _filter_provision_data(config_data, "agent", os_type, os_branch=None):
        yield agent_data


def ec2_autoinjection_install_data(os_type, os_branch=None):
    config_data = _load_provision()
    for autoinjection_data in config_data["autoinjection"]:
        for autoinjection_language_data in autoinjection_data:
            for autoinjection_env_data in _filter_provision_data(
                autoinjection_data, autoinjection_language_data, os_type, os_branch
            ):
                autoinjection_env_data["language"] = autoinjection_language_data
                yield autoinjection_env_data


def ec2_language_variants_install_data(language, os_type, os_branch=None):
    config_data = _load_provision()
    for language_variants_data in config_data["language-variants"]:
        for filtered_language_variants_data in _filter_provision_data(
            language_variants_data, language, os_type, os_branch
        ):
            yield filtered_language_variants_data


def ec2_weblogs_install_data(language, support_version, os_type, os_branch=None):
    config_data = _load_provision()
    for language_weblog_data in config_data["weblogs"]:
        for filtered_weblog_data in _filter_provision_data(language_weblog_data, language, os_type, os_branch):
            if support_version in filtered_weblog_data["supported-language-versions"]:
                yield filtered_weblog_data


def _filter_install_data(data, os_type, os_branch=None):
    # Filter by os_type
    filteredInstalations = [
        agent_data_install for agent_data_install in data["install"] if agent_data_install["os_type"] == os_type
    ]

    # Filter by os_branch: If yaml has os_branch we filter with os_branch
    if os_branch is not None:
        filteredInstalations = [
            agent_data_install
            for agent_data_install in filteredInstalations
            if ("os_branch" in agent_data_install and agent_data_install["os_branch"] == os_branch)
            or ("os_branch" not in agent_data_install)
        ]

    # Only one instalation per os_type or os_branch
    if len(filteredInstalations) > 1:
        raise Exception("Only one type of agent installation is allowed!", os_type, os_branch)

    return filteredInstalations


def _filter_provision_data(config_data, node_name, os_type, os_branch=None):
    filtered_data = []
    if node_name in config_data:
        for provision_data in config_data[node_name]:
            filteredInstalations = _filter_install_data(provision_data, os_type, os_branch)
            # No agent instalation for this os_type/branch. Skip it
            if not filteredInstalations:
                continue
            provision_data["install"] = filteredInstalations[0]
            filtered_data.append(provision_data)
    return filtered_data


def _load_provision():
    # Open the file and load the file
    with open("provision.yml") as f:
        config_data = yaml.load(f, Loader=SafeLoader)
    return config_data
