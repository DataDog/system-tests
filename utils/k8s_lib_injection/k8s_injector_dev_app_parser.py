import yaml
from utils.k8s_lib_injection.k8s_weblog import K8sWeblogSpecs
from utils._logger import logger


class InjectorDevAppConfigParser:
    def __init__(self, yaml_file):
        self.yaml_file = yaml_file
        self.app_data = self.load_yaml()

    def load_yaml(self):
        """Loads YAML file and extracts the first application under 'helm/apps'."""
        with open(self.yaml_file, "r") as file:
            data = yaml.safe_load(file)

        apps = data.get("helm", {}).get("apps", [])
        return apps[0] if apps else None  # Take the first app

    def parse_app(self):
        """Parses the first app and maps it to K8sWeblogSpecs."""
        if not self.app_data:
            return None

        pod_name = self.app_data.get("name", "default-app")
        namespace = self.app_data.get("namespace", "default")

        # Extract labels
        weblog_labels = self.app_data.get("values", {}).get("podLabels", {"app": pod_name})

        # Extract environment variables
        env_list = self.app_data.get("values", {}).get("env", [])
        weblog_env = {env["name"]: env["value"] for env in env_list}

        return K8sWeblogSpecs(
            pod_name=pod_name, weblog_env=weblog_env, weblog_labels=weblog_labels, namespace=namespace
        )


if __name__ == "__main__":
    parser = InjectorDevAppConfigParser(
        "/Users/roberto.montero/Documents/development/injector-dev/examples/single_service.yaml"
    )
    weblog_specs = parser.parse_app()

    if weblog_specs:
        logger.info(f"weblog_specs.pod_name:  {weblog_specs.pod_name}")
        logger.info(f"weblog_specs.weblog_env:  {weblog_specs.weblog_env}")
        logger.info(f"weblog_specs.weblog_labels:  {weblog_specs.weblog_labels}")
        logger.info(f"weblog_specs.namespace:  {weblog_specs.namespace}")

    else:
        logger.info("No applications found in helm/apps.")
