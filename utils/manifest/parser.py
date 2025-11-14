from collections.abc import Callable
from typing import Any
from collections import defaultdict
import yaml
from utils.manifest.declaration import Declaration

def field_processing(
    name: str,
    transformation: Callable[[str, list[dict[str, Any]], dict[str, Any]], None],
    value: list[dict[str, Any]],
    entry: dict[str, Any],
) -> None:
    if name in entry:
        return transformation(name, value, entry) or ([], True)
    return [], True


def process_lib_version(n: str, _: object, e: dict[str, Any]) -> None:
    e[n] = Declaration(e[n]).value

def process_variant_declaration(n: str, v: object, e: dict[str, Any]) -> None:
    new_entries = []
    all_variants = []
    for variant, _ in e[n].items():
        if variant != "*":
            all_variants.append(variant)
    for variant, raw_declaration in e[n].items():
        new_entry = {}
        if variant == "*":
            new_entry["excluded_variant"] = all_variants
        else:
            new_entry["variant"] = variant
        declaration = Declaration(raw_declaration, is_inline=True)
        if declaration.is_skip:
            new_entry["declaration"] = str(declaration)
        else:
            new_entry["excluded_library_version"] = declaration.value
            new_entry["declaration"] = "missing_feature"
        new_entries.append(new_entry)
    return new_entries, False


def _load_file(file: str, component: str):
    try:
        with open(file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return {}

    field_processors = [
            ("library_version", process_lib_version),
            ("excluded_library_version", process_lib_version),
            ("variant_declaration", process_variant_declaration),
            ]

    ret = {}
    for nodeid, raw_value in data["manifest"].items():
        if isinstance(raw_value, str):
            declaration = Declaration(raw_value, is_inline=True)
            value = {}
            if declaration.is_skip:
                value["declaration"] = str(declaration)
            else:
                value["excluded_library_version"] = declaration.value
                value["declaration"] = "missing_feature"
            value["library"] = component
            value = [value]
        else:
            if not isinstance(raw_value, list):
                raw_value = [raw_value]
            value = []
            for entry in raw_value:
                for field_processor in field_processors:
                    new_entries, keep_entry = field_processing(field_processor[0], field_processor[1], raw_value, entry)
                    value += new_entries
                if keep_entry:
                    value.append(entry)

        for entry in value:
            entry["library"] = component
        ret[nodeid] = value

    return ret


# @lru_cache
def load(base_dir: str = "manifests/") -> dict[str, dict[str, str]]:
    """Returns a dict of nodeid, value are another dict where the key is the component
        and the value the declaration. It is meant to sent directly the value of a nodeid to @released.

    Data example:

    {
        "tests/test_x.py::Test_feature":
        {
            "agent": "v1.0",
            "php": "missing_feature"
        }
    }
    """

    result = defaultdict(dict)

    for component in (
        "agent",
        "cpp",
        "cpp_httpd",
        "cpp_nginx",
        "dotnet",
        "golang",
        "java",
        "nodejs",
        "php",
        "python",
        "python_otel",
        "ruby",
        "rust",
        "dd_apm_inject",
        "k8s_cluster_agent",
        "python_lambda",
    ):
        data = _load_file(f"{base_dir}{component}.yml", component)

        for nodeid, value in data.items():
            if nodeid not in result:
                result[nodeid] = []
            result[nodeid] += value

    return result
