from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import Any

import yaml

from .const import TestDeclaration
from .declaration import Declaration
from .types import Condition, ManifestData, SkipDeclaration, SemverRange

YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

ALL_MANIFEST_COMPONENTS: tuple[str, ...] = (
    "agent",
    "c",
    "cpp",
    "cpp_httpd",
    "cpp_kong",
    "cpp_nginx",
    "dotnet",
    "golang",
    "java",
    "java_lambda",
    "java_otel",
    "nodejs",
    "nodejs_lambda",
    "nodejs_otel",
    "php",
    "python",
    "python_otel",
    "ruby",
    "rust",
    "dd_apm_inject",
    "k8s_cluster_agent",
    "python_lambda",
    "ruby_lambda",
    "envoy",
    "haproxy",
)

_CONDITION_SCALAR_TYPES: dict[str, type] = {
    "declaration": SkipDeclaration,
    "component": str,
    "component_version": SemverRange,
    "excluded_component_version": SemverRange,
}

_CONDITION_LIST_TYPES: dict[str, type] = {
    "weblog": str,
    "excluded_weblog": str,
}

_CONDITION_VALID_FIELDS: frozenset[str] = frozenset(
    ("component_version", "excluded_component_version", "weblog", "excluded_weblog", "declaration")
)


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


def check_condition(condition: Condition) -> None:
    for key, item in condition.items():
        if key in _CONDITION_SCALAR_TYPES:
            expected_type = _CONDITION_SCALAR_TYPES[key]
            if not isinstance(item, expected_type):
                raise TypeError(f"Wrong type for {key}, expected {expected_type} got {type(item)}")
        elif key in _CONDITION_LIST_TYPES:
            if not isinstance(item, list):
                raise TypeError(f"Wrong type for {key}, expected {list} got {type(item)}")
            inner_type = _CONDITION_LIST_TYPES[key]
            for e in item:
                if not isinstance(e, inner_type):
                    raise TypeError(f"Wrong type for {key}, expected {inner_type} got {type(e)}")
        else:
            raise AssertionError(f"The type of {key} should be added to the check_condition function")


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
        if key not in _CONDITION_VALID_FIELDS:
            raise ValueError(f"Field {key} unknown")

    return condition


def parse_weblogs(weblogs: str) -> list[str]:
    return [w.strip() for w in weblogs.split(",")]


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
        if n == "weblog":
            res = []
            for w in e[n]:
                if not isinstance(w, str):
                    continue
                res.extend(parse_weblogs(w))
            e[n] = res

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
            if not isinstance(weblog, str):
                continue
            if weblog != "*":
                all_weblogs.extend(parse_weblogs(weblog))
        for weblog, raw_declaration in e[n].items():
            condition = process_inline(raw_declaration, component)
            if weblog == "*":
                condition["excluded_weblog"] = all_weblogs
            else:
                condition["weblog"] = parse_weblogs(weblog)
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
            data = yaml.load(f, Loader=YAML_LOADER)  # noqa: S506
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


def load(base_dir: Path = Path("manifests/"), components: Iterable[str] | None = None) -> ManifestData:
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

    if components is None:
        selected_components: Iterable[str] = ALL_MANIFEST_COMPONENTS
    else:
        requested = set(components)
        selected_components = [c for c in ALL_MANIFEST_COMPONENTS if c in requested]

    for component in selected_components:
        data = _load_file(base_dir.joinpath(f"{component}.yml"), component)

        for nodeid, value in data.items():
            if nodeid not in result:
                result[nodeid] = []
            result[nodeid] += value

    return result
