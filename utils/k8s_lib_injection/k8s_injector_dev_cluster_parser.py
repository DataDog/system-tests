import yaml
import json
from utils._logger import logger


class InjectorDevClusterConfigParser:
    def __init__(self, yaml_file):
        self.yaml_file = yaml_file
        self.config_data = self.load_yaml()

    def load_yaml(self):
        """Loads YAML file and extracts the 'helm/config' node."""
        with open(self.yaml_file, "r") as file:
            data = yaml.safe_load(file)

        # Navigate to the "helm/config" node safely
        return data.get("helm", {}).get("config", {})

    def flatten_dict(self, d, parent_key=""):
        """Recursively flattens a dictionary, handling lists with indexes."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k

            if isinstance(v, dict):
                items.extend(self.flatten_dict(v, new_key).items())
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    if isinstance(item, dict):
                        items.extend(self.flatten_dict(item, f"{new_key}[{i}]").items())
                    else:
                        items.append((f"{new_key}[{i}]", str(item)))  # Convert list items to strings

            else:
                items.append((new_key, str(v)))

        return dict(items)

    def generate_json_properties(self):
        """Converts config data into JSON-style properties."""
        flat_config = self.flatten_dict(self.config_data)
        # return {key: str(value).lower() if isinstance(value, bool) else str(value) for key, value in flat_config.items()}
        return {key: str(value) for key, value in flat_config.items()}  # Ensure all values are strings

    def save_to_json(self, output_file="config_properties.json"):
        """Saves the parsed config properties to a JSON file."""
        properties = self.generate_json_properties()
        with open(output_file, "w") as file:
            json.dump(properties, file, indent=4)
        logger.info(f"✅ Config properties saved to {output_file}")

    def merge_helm_config_to_datadog_values(self, source_file: str, target_file: str, extra_props: dict = None):  # noqa: RUF013
        # Load source YAML (single_service.yaml)
        with open(source_file, "r") as src:
            source_yaml = yaml.safe_load(src)
            config_data = source_yaml.get("helm", {}).get("config", {})

        if not config_data:
            logger.info("No config found under 'helm/config'. Nothing to merge.")
            return

        # Load target YAML (datadog-helm-chart-values.yaml)
        with open(target_file, "r") as tgt:
            target_yaml = yaml.safe_load(tgt)

        # Ensure 'datadog' key exists in the target
        if "datadog" not in target_yaml:
            target_yaml["datadog"] = {}

        # Merge config data into datadog section
        def recursive_merge(source, target):
            for key, value in source.items():
                if isinstance(value, dict):
                    node = target.setdefault(key, {})
                    recursive_merge(value, node)
                else:
                    target[key] = value

        def set_nested_property(base_dict, dotted_key, value):
            """Given 'a.b.c': val, set base_dict['a']['b']['c'] = val."""
            keys = dotted_key.split(".")
            d = base_dict
            for k in keys[:-1]:
                d = d.setdefault(k, {})
            d[keys[-1]] = value

        recursive_merge(config_data.get("datadog", {}), target_yaml["datadog"])

        # Merge extra dotted properties
        if extra_props:
            for key, value in extra_props.items():
                set_nested_property(target_yaml, key, value)

        # Save updated target YAML
        with open(target_file, "w") as tgt:
            yaml.dump(target_yaml, tgt, sort_keys=False)

        logger.info(f"✅ Merged 'helm/config' into '{target_file}' under 'datadog' section.")

    def update_ddtrace_versions(self, file_path: str, lang_key: str, lang_value: str):
        """Adds or updates a key-value under all 'ddTraceVersions' in a YAML file."""

        def recursive_update(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "ddTraceVersions" and isinstance(value, dict):
                        value[lang_key] = lang_value
                    else:
                        recursive_update(value)
            elif isinstance(node, list):
                for item in node:
                    recursive_update(item)

        # Load YAML
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)

        # Update ddTraceVersions
        recursive_update(data)

        # Write back to the file
        with open(file_path, "w") as f:
            yaml.dump(data, f, sort_keys=False)

        logger.info(f"✅ Updated all ddTraceVersions with {lang_key}: {lang_value}")


if __name__ == "__main__":
    parser = InjectorDevClusterConfigParser(
        "/Users/roberto.montero/Documents/development/injector-dev/examples/single_service.yaml"
    )
    properties = parser.generate_json_properties()

    # logger.info properties in "key:value" format
    for key, value in properties.items():
        logger.info(f"{key}:{value}")

    # Save to JSON file
    # parser.save_to_json()
    parser.merge_helm_config_to_datadog_values(
        "/Users/roberto.montero/Documents/development/injector-dev/examples/single_service.yaml",
        "/Users/roberto.montero/Documents/development/system-tests/logs_k8s_lib_injection_all_namespaces/lib-injection-testing_help_values.yaml",
    )
