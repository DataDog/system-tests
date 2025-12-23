from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import ruamel.yaml
from utils._context.component_version import Version
from utils.manifest._internal.rule import match_condition
from utils.manifest._internal.types import SemverRange as CustomSpec
from utils.manifest import Manifest
from ruamel.yaml import CommentedMap, YAML, CommentedSeq

from utils.manifest import Condition, SkipDeclaration
from .const import LIBRARIES
import sys
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .types import Context

# Fix line wrapping bug in ruamel
ruamel.yaml.emitter.Emitter.MAX_SIMPLE_KEY_LENGTH = 1000


class ManifestEditor:
    raw_data: dict[str, CommentedMap]
    manifest: Manifest
    round_trip_parser: YAML
    context: Context
    poked_views: dict[View, set[Context]]
    added_rules: dict[str, set[tuple[View, Context]]]

    @dataclass
    class View:
        """View on a manifest element"""

        rule: str
        condition: Condition
        condition_index: int
        clause_key: str | None
        is_inline: bool = False

        def __hash__(self) -> int:
            return hash(self.rule + str(self.condition) + str(self.condition_index))

    def __init__(self, weblogs: dict[str, set[str]], manifests_path: Path = Path("manifests/")):
        self.init_round_trip_parser()

        self.raw_data = {}
        for component in LIBRARIES:
            self.raw_data[component] = self.round_trip_parser.load(manifests_path.joinpath(f"{component}.yml"))

        self.manifest = Manifest(path=manifests_path)
        self.poked_views = {}
        self.added_rules = {}
        self.weblogs = weblogs

    def init_round_trip_parser(self) -> None:
        self.round_trip_parser = YAML()
        self.round_trip_parser.explicit_start = True
        self.round_trip_parser.width = 10000
        self.round_trip_parser.comment_column = 10000
        self.round_trip_parser.allow_unicode = True
        self.round_trip_parser.default_flow_style = False
        self.round_trip_parser.preserve_quotes = True
        self.round_trip_parser.indent(mapping=2, sequence=4, offset=2)

    def set_context(self, context: Context) -> ManifestEditor:
        self.context = context
        self.manifest.update_rules(context.library, context.library_version, context.variant)
        return self

    def get_matches(self, nodeid: str) -> set[View]:
        def compute_edit_loc(raw_conditions: list[CommentedMap], parsed_rule_index: int) -> tuple[int, bool]:
            index = -1
            hidden_length = 0
            is_clause = False

            for condition in raw_conditions:
                if index + hidden_length == parsed_rule_index:
                    return index, is_clause
                index += 1

                is_clause = False
                if weblog_declaration := condition.get("weblog_declaration"):
                    hidden_length += len(weblog_declaration)
                    if index + hidden_length >= parsed_rule_index:
                        is_clause = True

            return index, is_clause

        declaration_sources: list[tuple[str, list[tuple[int, int]]]] = []
        ret = set()

        _ = self.manifest.get_declarations(nodeid, declaration_sources)

        for rule, condition_indices in declaration_sources:
            for condition_index in condition_indices:
                component = self.manifest.data[rule][condition_index[0]]["component"]
                if component not in LIBRARIES:
                    continue
                raw_conditions = self.raw_data[component]["manifest"][rule]
                parsed_condition = self.manifest.data[rule][condition_index[0]]
                index, is_clause = (
                    (condition_index[1], False)
                    if isinstance(raw_conditions, str)
                    else compute_edit_loc(raw_conditions, condition_index[1])
                )

                clause_key = None
                if is_clause:
                    key_list = parsed_condition.get("weblog", ["*"])
                    assert key_list
                    assert len(key_list) == 1
                    clause_key = key_list[0]

                ret.add(
                    ManifestEditor.View(
                        rule,
                        parsed_condition,
                        index,
                        clause_key,
                        isinstance(raw_conditions, str),
                    )
                )
        return ret

    def poke(self, view: View) -> None:
        if view not in self.poked_views:
            self.poked_views[view] = set()
        self.poked_views[view].add(self.context)

    def update(self, view: View, new_content: Condition | SkipDeclaration | str, append_key: str | None = None) -> None:
        if isinstance(new_content, SkipDeclaration):
            new_content = str(new_content)

        raw_data = self.raw_data[view.condition["component"]]["manifest"]

        if view.is_inline:
            raw_data[view.rule] = new_content
        elif view.clause_key and append_key:
            raw_data[view.rule][view.condition_index]["weblog_declaration"][append_key] = new_content
        elif view.clause_key:
            raw_data[view.rule][view.condition_index]["weblog_declaration"][view.clause_key] = new_content
        else:
            raw_data[view.rule][view.condition_index] = new_content

    def add_condition(self, rule: str, condition: dict) -> None:
        print(type(self.raw_data), type(self.raw_data[rule]), self.raw_data[rule])
        self.raw_data[self.context.library]["manifest"][rule].append(condition)

    def add_rules(self, rules: list[str], parent: View) -> None:
        for rule in rules:
            if rule not in self.added_rules:
                self.added_rules[rule] = set()
            self.added_rules[rule].add((parent, self.context))

    def contains(self, rule: str) -> bool:
        return rule in self.raw_data[self.context.library]["manifest"]

    @staticmethod
    def serialize_condition(condition: Condition) -> dict[str, str]:
        ret = {}
        for name, value in condition.items():
            if name == "declaration":
                ret[name] = str(value)
            elif name == "component":
                pass
            elif name in ("weblog", "excluded_weblog"):
                if isinstance(value, list):
                    if len(value) == 1:
                        ret[name] = value[0]
                    else:
                        ret[name] = CommentedSeq(value)
                        ret[name].fa.set_flow_style()
                else:
                    ret[name] = value
            else:
                ret[name] = str(value)
        return ret

    @staticmethod
    def specialize(condition: Condition, context: Context) -> Condition:
        ret = condition.copy()
        ret["weblog"] = [context.variant]
        ret["component_version"] = CustomSpec(f">={context.library_version}")
        return ret

    def build_new_rules(self) -> dict[str, list[Condition]]:
        ret: dict[str, list[Condition]] = {}
        for rule, sources in self.added_rules.items():
            for source in sources:
                condition = source[0].condition
                if rule not in ret:
                    ret[rule] = []
                ret[rule].append(ManifestEditor.specialize(condition, source[1]))
        return ret

    @staticmethod
    def condition_key(condition: Condition) -> tuple:
        ret = []
        clauses = sorted(condition.items())
        for name, value in clauses:
            if isinstance(value, list):
                ret.append((name, tuple(value)))
            else:
                ret.append((name, value))
        return tuple(ret)

    @staticmethod
    def compress_pokes(contexts: set[Context]) -> tuple[Version, list[str]]:
        ret: tuple[Version, list[str]] | None = None
        for context in contexts:
            if not ret:
                ret = (context.library_version, [])
            ret[1].append(context.variant)
        assert ret
        return ret

    def compress_rules(self, rules: dict[str, list[Condition]]) -> dict[str, list[Condition]]:
        compressed: dict[str, dict[tuple, set[str]]] = {}
        ret: dict[str, list[Condition]] = {}
        non_var_conditions: dict[tuple, Condition] = {}
        for rule, conditions in rules.items():
            if rule not in compressed:
                compressed[rule] = {}
            for condition in conditions:
                non_var_condition = condition.copy()
                del non_var_condition["weblog"]
                key = ManifestEditor.condition_key(non_var_condition)

                non_var_conditions[key] = non_var_condition

                if key not in compressed[rule]:
                    compressed[rule][key] = set()

                compressed[rule][key] |= set(condition.get("weblog", []))

        for rule, conditions in compressed.items():
            if rule not in ret:
                ret[rule] = []
            for condition_key, weblogs in conditions.items():
                condition = non_var_conditions[condition_key]
                if set(weblogs) != self.weblogs[condition["component"]]:
                    condition["weblog"] = list(weblogs)
                ret[rule].append(condition)
        return ret

    def write_new_rules(self) -> None:
        new_rules = self.build_new_rules()
        new_rules = self.compress_rules(new_rules)
        for rule, conditions in new_rules.items():
            for condition in conditions:
                manifest = self.raw_data[condition["component"]]["manifest"]
                if rule not in manifest:
                    manifest[rule] = []
                manifest[rule].append(self.serialize_condition(condition))

    def write_poke(self) -> None:
        for view, contexts in self.poked_views.items():
            raw_data = self.raw_data[view.condition["component"]]["manifest"][view.rule]
            component_version, weblogs = ManifestEditor.compress_pokes(contexts)
            all_weblogs = set(weblogs) == self.weblogs[view.condition["component"]]

            if view.is_inline:
                if "excluded_component_version" in view.condition:
                    # TODO: Add comment to signal that there is a version problem
                    print("test")
                    continue
                self.raw_data[view.condition["component"]]["manifest"][view.rule] = [
                    {
                        "declaration": str(view.condition["declaration"]),
                        "component_version": f"<{component_version}",
                    },
                ]
                raw_data = self.raw_data[view.condition["component"]]["manifest"][view.rule]

                if not all_weblogs:
                    raw_data.append(
                        {
                            "declaration": str(view.condition["declaration"]),
                            "excluded_weblog": CommentedSeq(weblogs.copy()),
                        },
                    )
                    raw_data[0]["weblog"] = CommentedSeq(weblogs.copy())

                    raw_data[1]["excluded_weblog"].fa.set_flow_style()
                    raw_data[0]["weblog"].fa.set_flow_style()

            elif "weblog_declaration" in raw_data[view.condition_index]:
                for weblog in weblogs:
                    raw_data[view.condition_index]["weblog_declaration"][weblog] = f"v{component_version}"

            else:
                raw_data[view.condition_index]["excluded_weblog"] = CommentedSeq(
                    view.condition.get("excluded_weblog", []) + weblogs
                )
                raw_data[view.condition_index]["excluded_weblog"].fa.set_flow_style()
                raw_data.append(
                    {
                        "declaration": str(view.condition["declaration"]),
                        "excluded_component_version": f">={component_version}",
                    }
                )

                if not all_weblogs:
                    raw_data[-1]["weblog"] = CommentedSeq(weblogs.copy())
                    raw_data[-1]["weblog"].fa.set_flow_style()

    def write(self, output_dir: Path = Path("manifests/")) -> None:
        self.write_new_rules()
        self.write_poke()
        for component, data in self.raw_data.items():
            file = output_dir.joinpath(f"{component}.yml")
            self.round_trip_parser.dump(data, file)
            if False:
                self.round_trip_parser.dump(data, sys.stdout)
            data = file.read_text()
            file.write_text(
                f"# yaml-language-server: $schema=https://raw.githubusercontent.com/DataDog/system-tests/refs/heads/main/utils/manifest/schema.json\n{data}"
            )
