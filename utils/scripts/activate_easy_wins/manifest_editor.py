from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import ruamel.yaml
from utils._decorators import CustomSpec
from utils.manifest import Manifest
from ruamel.yaml import CommentedMap, YAML

from utils.manifest import Condition, SkipDeclaration
from .const import LIBRARIES
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import Context

# Fix line wrapping bug in ruamel
ruamel.yaml.emitter.Emitter.MAX_SIMPLE_KEY_LENGTH = 1000


class ManifestEditor:
    raw_data: dict[str, CommentedMap]
    manifest: Manifest
    round_trip_parser: YAML
    context: Context
    poked_views: dict[View, set[Context]] = {}
    added_rules: dict[str, set[tuple[View, Context]]] = {}

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

    def __init__(self, manifests_path: Path = Path("manifests/")):
        self.init_round_trip_parser()

        self.raw_data = {}
        for component in LIBRARIES:
            self.raw_data[component] = self.round_trip_parser.load(manifests_path.joinpath(f"{component}.yml"))

        self.manifest = Manifest()

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
            else:
                ret[name] = str(value)
        return ret

    @staticmethod
    def specialize(condition: Condition, context: Context) -> Condition:
        condition["weblog"] = [context.variant]
        condition["component_version"] = CustomSpec(f">={context.library_version}")
        return condition

    def write_new_rules(self) -> None:
        for rule, sources in self.added_rules.items():
            for source in sources:
                condition = source[0].condition
                manifest = self.raw_data[condition["component"]]["manifest"]
                if rule not in manifest:
                    manifest[rule] = []
                manifest[rule].append(self.serialize_condition(ManifestEditor.specialize(condition, source[1])))

    def write(self, output_dir: Path = Path("manifests/")) -> None:
        self.write_new_rules()
        for component, data in self.raw_data.items():
            self.round_trip_parser.dump(data, sys.stdout)
            if False:
                self.round_trip_parser.dump(data, output_dir.joinpath(f"{component}.yml"))
