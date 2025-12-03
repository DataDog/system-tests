from collections.abc import Callable
from typing import Any
from collections import defaultdict
import yaml
from utils.manifest.declaration import Declaration


def field_processing(
    name: str,
    transformation: Callable[[str, list[dict[str, Any]], dict[str, Any]], tuple[list[dict[str, Any]], bool] | None],
    value: list[dict[str, Any]],
    entry: dict[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    if name in entry:
        return transformation(name, value, entry) or ([], True)
    return [], True


def process_lib_version(n: str, _: object, e: dict[str, Any]) -> tuple[list[dict[str, Any]], bool] | None:
    e[n] = Declaration(e[n]).value
    return None


def process_weblog_declaration(n: str, _v: object, e: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    new_entries: list[dict[str, Any]] = []
    all_weblogs: list[str] = []
    for weblog in e[n]:
        if weblog != "*":
            all_weblogs.append(weblog)
    for weblog, raw_declaration in e[n].items():
        new_entry: dict[str, Any] = {}
        if weblog == "*":
            new_entry["excluded_weblog"] = all_weblogs
        else:
            new_entry["weblog"] = weblog
        declaration = Declaration(raw_declaration, is_inline=True)
        if declaration.is_skip:
            new_entry["declaration"] = declaration
        else:
            new_entry["excluded_component_version"] = declaration.value
            new_entry["declaration"] = Declaration("missing_feature")
        new_entries.append(new_entry)
    return new_entries, False


def _load_file(file: str, component: str) -> dict[str, list[dict[str, Any]]]:
    try:
        with open(file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return {}

    field_processors = [
        ("component_version", process_lib_version),
        ("excluded_component_version", process_lib_version),
        ("weblog_declaration", process_weblog_declaration),
    ]

    ret: dict[str, list[dict[str, Any]]] = {}
    for nodeid, raw_value in data["manifest"].items():
        if isinstance(raw_value, str):
            declaration = Declaration(raw_value, is_inline=True)
            value: dict[str, Any] = {}
            if declaration.is_skip:
                value["declaration"] = declaration
            else:
                value["excluded_component_version"] = declaration.value
                value["declaration"] = Declaration("missing_feature")
            value["component"] = component
            value_list = [value]
        else:
            raw_value_list = raw_value if isinstance(raw_value, list) else [raw_value]
            value_list = []
            for entry in raw_value_list:
                for field_processor in field_processors:
                    new_entries, keep_entry = field_processing(
                        field_processor[0], field_processor[1], raw_value_list, entry
                    )
                    value_list += new_entries
                if keep_entry:
                    value_list.append(entry)

        for entry in value_list:
            entry["component"] = component
        ret[nodeid] = value_list

    return ret


# @lru_cache
def load(base_dir: str = "manifests/") -> dict[str, list[dict[str, Any]]]:
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

    result: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

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
