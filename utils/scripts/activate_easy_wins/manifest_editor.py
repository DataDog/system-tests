from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import ruamel.yaml
from utils.manifest import Manifest
from ruamel.yaml import CommentedMap, YAML

from utils.manifest import Condition, SkipDeclaration
from .const import LIBRARIES
from .types import Context

# Fix line wrapping bug in ruamel
ruamel.yaml.emitter.Emitter.MAX_SIMPLE_KEY_LENGTH = 1000


class ManifestEditor:
    raw_data: dict[str, CommentedMap]
    manifest: Manifest
    round_trip_parser: YAML

    @dataclass
    class View:
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

    def set_context(self, context: Context) -> None:
        self.manifest.update_rules(context.library, context.library_version, context.variant)

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

        dec = self.manifest.get_declarations(nodeid, declaration_sources)

        for rule, condition_indices in declaration_sources:
            for condition_index in condition_indices:
                component = self.manifest.data[rule][condition_index[0]]["component"]
                raw_conditions = self.raw_data[component]["manifest"][rule]
                parsed_condition = self.manifest.data[rule][condition_index[0]]
                index, is_clause = (
                    (condition_index[1], False)
                    if isinstance(raw_conditions, str)
                    else compute_edit_loc(raw_conditions, condition_index[1])
                )

                clause_key = None
                if is_clause:
                    clause_key = parsed_condition.get("weblog", ["*"])
                    assert len(clause_key) == 1
                    clause_key = clause_key[0]

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

    def write(self, output_dir: Path = Path("manifests/")) -> None:
        for component, data in self.raw_data.items():
            self.round_trip_parser.dump(data, output_dir.joinpath(f"{component}.yml"))
