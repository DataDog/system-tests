from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import Any, get_args, get_origin

import yaml

from .const import TestDeclaration
from .declaration import Declaration
from .types import Condition, ManifestData, SkipDeclaration, SemverRange


def process_inline(raw_declaration: str, component: str) -> Condition:
    declaration = Declaration(raw_declaration, component, is_inline=True)
    if declaration.is_skip:
        assert isinstance(declaration.value, TestDeclaration)
        condition: Condition = {
            "component": component,
            "declaration": SkipDeclaration(declaration.value, declaration.reason),
        }
    else:
        assert isinstance(declaration.value, SemverRange)
        condition: Condition = {
            "declaration": SkipDeclaration("missing_feature", f"declared version for {component} is {raw_declaration}"),
            "excluded_component_version": declaration.value,
            "component": component,
        }
    return condition


def check_condition(condition: Condition):
    def type_check(key: str, value: Any, expected_type: type):  # noqa: ANN401
        if not isinstance(value, expected_type):
            raise TypeError(f"Wrong type for {key}, expected {expected_type} got {type(value)}")

    def type_check_list(key: str, value: Any, inner_type: type):  # noqa: ANN401
        type_check(key, value, list)
        for e in value:
            type_check(key, e, inner_type)

    types = {
        "declaration": SkipDeclaration,
        "component": str,
        "component_version": SemverRange,
        "excluded_component_version": SemverRange,
        "weblog": list[str],
        "excluded_weblog": list[str],
    }

    for key, item in condition.items():
        assert key in types, f"The type of {key} should be added to the check_condition function"
        if get_origin(types[key]) is list:
            (inner_type,) = get_args(types[key])
            type_check_list(key, item, inner_type)
        else:
            type_check(key, item, types[key])


def cast_to_condition(entry: dict, component: str) -> Condition:
    """Transforms a regular dict to a Condition doing type checking. Any
    transformation should be made in a FieldProcessor function.
    """

    condition: Condition = {"component": component, "declaration": entry["declaration"]}

    if "component_version" in entry:
        condition["component_version"] = entry["component_version"]
    if "excluded_component_version" in entry:
        condition["excluded_component_version"] = entry["excluded_component_version"]
    if "weblog" in entry:
        condition["weblog"] = entry["weblog"]
    if "excluded_weblog" in entry:
        condition["excluded_weblog"] = entry["excluded_weblog"]

    check_condition(condition)
    for key in entry:
        if key not in ["component_version", "excluded_component_version", "weblog", "excluded_weblog", "declaration"]:
            raise ValueError(f"Field {key} unknown")

    return condition


class FieldProcessor:
    """Contains all processing functions that should be applied to raw fields from
    the manifest files.

    To process a new field you should add the appropriate processing function
    implementing the following interface:
        @staticmethod
        @processor
        def my_processor(key: str, entry: dict[str, Any], component: str):
            ...
    Where:
        key (str): the field name that the processor is applied to
        entry (dict[str, Any]): the raw entry that was read from the manifest file
        component (str): the manifest component name

    You should then add it to the field_processors alongside the target field name.
    If you are looking to add support for a new field type you should also make sure
    to check if cast to condition needs to be updated.
    """

    @dataclass
    class Return:
        """Return type for all field processor.

        Args:
            new_conditions (list[Condition]): conditions that are derived by the
                processed item and should be added to the rule
            rule_entry_is_condition (bool): specifies if, based on the item processed,
                the raw entry should be parsed to a condition

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
    def component_version(n: str, e: dict[str, Any], component: str) -> None:
        e[n] = Declaration(e[n], component, is_inline=True).value

    @staticmethod
    @processor
    def ensure_list(n: str, e: dict[str, Any], _component: str) -> None:
        if not isinstance(e[n], list):
            e[n] = [e[n]]

    @staticmethod
    @processor
    def declaration(n: str, e: dict[str, Any], component: str) -> None:
        declaration = Declaration(e[n], component)
        assert isinstance(declaration.value, TestDeclaration)
        e[n] = SkipDeclaration(declaration.value, declaration.reason)

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
                condition["weblog"] = weblog if isinstance(weblog, list) else [weblog]
            new_entries.append(condition)
        return FieldProcessor.Return(new_entries, rule_entry_is_condition=False)

    field_processors = [
        ("component_version", component_version),
        ("excluded_component_version", component_version),
        ("weblog_declaration", weblog_declaration),
        ("declaration", declaration),
        ("weblog", ensure_list),
        ("excluded_weblog", ensure_list),
    ]


def _load_file(file: Path, component: str) -> ManifestData:
    try:
        with open(file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return ManifestData()

    field_processors = FieldProcessor.field_processors

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
                    try:
                        condition_list.append(cast_to_condition(entry, component))
                    except KeyError as e:
                        raise ValueError(
                            dedent(f"""
                            Error while casting
                                {nodeid}:
                                    {entry}
                            to Condition in {component} manifest. Field {e} is missing.
                            """)
                        ) from e
                    except ValueError as e:
                        raise ValueError(
                            dedent(f"""
                            Error while casting
                                {nodeid}:
                                    {entry}
                            to Condition in {component} manifest.
                            """)
                        ) from e
                    except TypeError as e:
                        raise TypeError(
                            dedent(f"""
                            Error while casting
                                {nodeid}:
                                    {entry}
                            to Condition in {component} manifest.
                            Make sure you are not missing a FieldProcessor
                            """)
                        ) from e

        for condition in condition_list:
            # Do not remove this check, it does run twice on some conditions but
            # it is placed here to ensure that it runs on all conditions at least
            # once. Unchecked conditions can lead to VERY HARD TO DETECT BUGS
            check_condition(condition)
        ret[nodeid] = condition_list

    return ret


def load(base_dir: Path = Path("manifests/")) -> ManifestData:
    """Transforms the following raw manifest data:
    --------------------------------------------------------------
    -------------------------------------------------------      |
    tests/dir/file.py::Class:                             |      |
    ------------------------------------------            | rule |
        - weblog: weblog1              field | entry      |      |
          component_version: <4.3.5    field |            |      |
          declaration: missing_feature field |            |      | raw_manifest
    -------------------------------------------------------      |
    tests/dir/file.py::Class::func:                       |      |
    ------------------------------------------            | rule |
        - weblog_declaration:          field | entry      |      |
            weblog1: v4.3.5                  |            |      |
    -------------------------------------------------------      |
    --------------------------------------------------------------

    Into:
    ------------------------------------------------------------------------------------
    {                                                                                  |
    -----------------------------------------------------------------------------      |
        "tests/dir/file.py::Class": [                                           |      |
    -----------------------------------------------------------------           |      |
            {                                                       |           |      |
                "component_version": SemverRange("<4.3.5"),         |           |      |
                "weblog: weblog1",                                  | Condition | rule |
                "declaration": SkipDeclaration("missing_feature")   |           |      |
            }                                                       |           |      |
    -----------------------------------------------------------------           |      |
        ]                                                                       |      |
    -----------------------------------------------------------------------------      | ManifestData
        "tests/dir/file.py::Class::func": [                                     |      |
    -----------------------------------------------------------------           |      |
            {                                                       |           |      |
                "component_version": SemverRange("<4.3.5"),         |           |      |
                "weblog: weblog1",                                  | Condition | rule |
                "declaration": SkipDeclaration("missing_feature")   |           |      |
            }                                                       |           |      |
    -----------------------------------------------------------------           |      |
        ]                                                                       |      |
    -----------------------------------------------------------------------------      |
    }                                                                                  |
    ------------------------------------------------------------------------------------
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
        data = _load_file(base_dir.joinpath(f"{component}.yml"), component)

        for nodeid, value in data.items():
            if nodeid not in result:
                result[nodeid] = []
            result[nodeid] += value

    return result
