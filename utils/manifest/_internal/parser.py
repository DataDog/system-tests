from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import yaml

from utils._decorators import CustomSpec as SemverRange
from utils._decorators import _TestDeclaration
from .declaration import Declaration
from .types import Condition, ManifestData, SkipDeclaration


def process_inline(raw_declaration: str, component: str) -> Condition:
    declaration = Declaration(raw_declaration, is_inline=True)
    if declaration.is_skip:
        assert isinstance(declaration.value, _TestDeclaration)
        condition: Condition = {
            "component": component,
            "declaration": SkipDeclaration(declaration.value, declaration.reason),
        }
    else:
        assert isinstance(declaration.value, SemverRange)
        condition: Condition = {
            "declaration": SkipDeclaration("missing_feature"),
            "excluded_component_version": declaration.value,
            "component": component,
        }
    return condition


def cast_to_condition(entry: dict, component: str) -> Condition:
    if not isinstance(entry["declaration"], SkipDeclaration):
        raise TypeError(f"Wrong value for declaration: {entry['declaration']}")
    condition: Condition = {"component": component, "declaration": entry["declaration"]}

    if entry["component_version"]:
        assert isinstance(entry["component_version"], SemverRange), (
            f"Wrong value for declaration: {entry['declaration']}"
        )
        condition["component_version"] = entry["component_version"]

    if entry["excluded_component_version"]:
        assert isinstance(entry["excluded_component_version"], SemverRange), (
            f"Wrong value for declaration: {entry['declaration']}"
        )
        condition["excluded_component_version"] = entry["excluded_component_version"]

    if entry["weblog"]:
        assert isinstance(entry["weblog"], str | list), f"Wrong value for declaration: {entry['declaration']}"
        condition["weblog"] = entry["weblog"]

    if entry["excluded_weblog"]:
        assert isinstance(entry["excluded_weblog"], str | list), f"Wrong value for declaration: {entry['declaration']}"
        condition["excluded_weblog"] = entry["excluded_weblog"]

    return condition


class FieldProcessor:
    @dataclass
    class Return:
        """Return type for all field processor.
        new_conditions -- conditions that are derived by the processed item
        rule_entry_is_condition -- specifies if, based on the item processed, the entry should be parsed to a condition
        """

        new_conditions: list[Condition] = field(default_factory=list)
        rule_entry_is_condition: bool = True

        def __iter__(self):
            yield self.new_conditions
            yield self.rule_entry_is_condition

    @staticmethod
    def processor(
        transformation: Callable[[str, dict[str, Any], str], Return | None],
    ) -> Callable:
        def field_processing(key: str, entry: dict[str, Any], component: str):
            if key in entry:
                return transformation(key, entry, component) or FieldProcessor.Return()
            return FieldProcessor.Return()

        return field_processing

    @staticmethod
    @processor
    def lib_version(n: str, e: dict[str, Any], _component: str) -> None:
        e[n] = Declaration(e[n]).value

    @staticmethod
    @processor
    def weblog_declaration(n: str, e: dict[str, Any], component: str) -> Return:
        new_entries: list[Condition] = []
        all_weblogs: list[str] = []
        for weblog in e[n]:
            if weblog != "*":
                all_weblogs.append(weblog)
        for weblog, raw_declaration in e[n].items():
            condition = process_inline(raw_declaration, component)
            if weblog == "*":
                condition["excluded_weblog"] = all_weblogs
            else:
                condition["weblog"] = weblog
            new_entries.append(condition)
        return FieldProcessor.Return(new_entries, rule_entry_is_condition=False)


def _load_file(file: str, component: str) -> ManifestData:
    try:
        with open(file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return ManifestData()

    field_processors = [
        ("component_version", FieldProcessor.lib_version),
        ("excluded_component_version", FieldProcessor.lib_version),
        ("weblog_declaration", FieldProcessor.weblog_declaration),
    ]

    ret: ManifestData = ManifestData()
    for nodeid, raw_value in data["manifest"].items():
        condition_list: list[Condition]
        if isinstance(raw_value, str):
            condition_list = [process_inline(raw_value, component)]
        else:
            condition_list = []
            for entry in raw_value:
                keep_entry = True
                for key, func in field_processors:
                    processor_return = func(key, entry, component)
                    keep_entry &= processor_return.rule_entry_is_condition
                    condition_list += processor_return.new_conditions
                if keep_entry:
                    condition_list.append(cast_to_condition(entry, component))

        ret[nodeid] = condition_list

    return ret


def load(base_dir: str = "manifests/") -> ManifestData:
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

    result: ManifestData = ManifestData()

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
