from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import ruamel.yaml
from utils.manifest._internal.const import TestDeclaration
from utils.manifest import Manifest
from ruamel.yaml import CommentedMap, YAML, CommentedSeq

from utils.manifest import Condition
from .const import LIBRARIES
from typing import TYPE_CHECKING
import re

if TYPE_CHECKING:
    from utils._context.component_version import Version
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

    def __init__(
        self,
        weblogs: dict[str, set[str]],
        manifests_path: Path = Path("manifests/"),
        components: list[str] | None = None,
    ):
        self.init_round_trip_parser()

        self.raw_data = {}
        components_to_process = components if components is not None else LIBRARIES
        for component in components_to_process:
            data = self.wrap_key_anchors(manifests_path.joinpath(f"{component}.yml"))
            self.raw_data[component] = self.round_trip_parser.load(data)

        self.manifest = Manifest(path=manifests_path)
        self.poked_views = {}
        self.added_rules = {}
        self.weblogs = weblogs

    def wrap_key_anchors(self, file: Path) -> str:
        """Wrap anchor references used as keys in quotes for ruamel.yaml parsing.

        Converts lines like:
            *django: v3.12.0.dev
            *django : v3.12.0.dev  (with space before colon)
        to:
            '*django': v3.12.0.dev
            '*django' : v3.12.0.dev

        This allows ruamel.yaml to parse anchor references used as unquoted keys.
        """
        lines = []
        for line in file.read_text().splitlines():
            # Match anchor reference with optional spaces before colon
            # Pattern: indentation, anchor ref, optional spaces, colon
            match = re.match(r"^(\s+)(\*[a-zA-Z_][a-zA-Z0-9_]*)(\s*)(:)", line)
            if match:
                indentation = match.group(1)
                anchor_ref = match.group(2)  # e.g., *django
                spaces_before_colon = match.group(3)  # Preserve any spaces before colon
                colon = match.group(4)
                rest_of_line = line[match.end() :]  # Everything after the colon
                lines.append(f"{indentation}'{anchor_ref}'{spaces_before_colon}{colon}{rest_of_line}")
            else:
                lines.append(line)
        return "\n".join(lines)

    def unwrap_key_anchors(self, content: str) -> str:
        """Unwrap anchor references used as keys, restoring them to unquoted state.

        Converts lines like:
            '*django': v3.12.0.dev
            '*django' : v3.12.0.dev  (with space before colon)
            "*django": v3.12.0.dev  (double quotes)
        to:
            *django: v3.12.0.dev
            *django : v3.12.0.dev

        This restores anchor references to their original unquoted format.
        """
        lines = []
        for line in content.splitlines():
            # Match quoted anchor reference with optional spaces before colon
            # Pattern: indentation, quote, anchor ref, quote, optional spaces, colon
            # Handles both single and double quotes
            match = re.match(r"^(\s+)(['\"])(\*[a-zA-Z_][a-zA-Z0-9_]*)\2(\s*)(:)", line)
            if match:
                indentation = match.group(1)
                anchor_ref = match.group(3)  # e.g., *django (without quotes)
                spaces_before_colon = match.group(4)  # Preserve any spaces before colon
                colon = match.group(5)
                rest_of_line = line[match.end() :]  # Everything after the colon
                lines.append(f"{indentation}{anchor_ref}{spaces_before_colon}{colon}{rest_of_line}")
            else:
                lines.append(line)
        return "\n".join(lines)

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
        self.manifest.update_rules({context.library: context.library_version}, context.variant)
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

    def add_rules(self, rules: list[str], parent: View) -> None:
        if "excluded_component_version" in parent.condition:
            return
        for rule in rules:
            if rule not in self.added_rules:
                self.added_rules[rule] = set()
            self.added_rules[rule].add((parent, self.context))

    @staticmethod
    def serialize_condition(condition: Condition) -> dict[str, str | CommentedSeq | dict]:
        if (
            "weblog" in condition
            and "component_version" in condition
            and condition["declaration"] == TestDeclaration.MISSING_FEATURE
            and not condition["declaration"].details
        ):
            return {"weblog_declaration": dict.fromkeys(condition["weblog"], str(condition["component_version"]))}

        if "weblog" in condition and "component_version" not in condition and len(condition) <= 3:  # noqa: PLR2004
            return {"weblog_declaration": dict.fromkeys(condition["weblog"], str(condition["declaration"]))}

        ret: dict[str, str | CommentedSeq] = {}
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
                        commented_seq = ret[name]
                        assert isinstance(commented_seq, CommentedSeq)
                        commented_seq.fa.set_flow_style()
                else:
                    ret[name] = str(value)
            else:
                ret[name] = str(value)
        return ret

    @staticmethod
    def specialize(condition: Condition, context: Context) -> Condition:
        ret = condition.copy()
        if "excluded_weblog" in ret:
            del ret["excluded_weblog"]
        ret["weblog"] = [context.variant]
        # ret["component_version"] = CustomSpec(f">={context.library_version}")
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
        ret: list[tuple[str, str | tuple[str]]] = []
        clauses = sorted(condition.items())
        for name, value in clauses:
            if isinstance(value, list):
                ret.append((name, tuple(value)))
            else:
                ret.append((name, str(value)))
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

        for rule, weblog_conditions in compressed.items():
            if rule not in ret:
                ret[rule] = []
            for condition_key, weblogs in weblog_conditions.items():
                condition = non_var_conditions[condition_key].copy()
                if set(weblogs) != self.weblogs[condition["component"]] and "parametric-" not in next(iter(weblogs)):
                    condition["weblog"] = list(weblogs)
                ret[rule].append(condition)
        return ret

    def write_comment(
        self,
        obj: CommentedMap | CommentedSeq,
        key_or_index: str | int,
        comment: str,
        position: str = "inline",
    ) -> None:
        """Add a comment to a YAML structure.

        Args:
            obj: The CommentedMap or CommentedSeq to add the comment to
            key_or_index: The key (for CommentedMap) or index (for CommentedSeq)
            comment: The comment text to add
            position: Where to place the comment - "before", "after", or "inline"

        """
        if not isinstance(obj, (CommentedMap, CommentedSeq)):
            return

        # ruamel.yaml adds the # automatically, so we don't include it in the comment text
        if isinstance(obj, CommentedMap):
            if not isinstance(key_or_index, str) or key_or_index not in obj:
                return
            if position == "before":
                obj.yaml_set_comment_before_after_key(key_or_index, after=comment)
            else:  # "after" or "inline" - both use end-of-line comments
                obj.yaml_add_eol_comment(comment, key=key_or_index)
        elif isinstance(obj, CommentedSeq):
            if not isinstance(key_or_index, int) or key_or_index < 0 or key_or_index >= len(obj):
                return
            # For sequences, use end-of-line comments for all positions
            obj.yaml_add_eol_comment(comment, key=key_or_index)

    def write_new_rules(self) -> None:
        def count_new_condition_per_component(new_conditions: list[Condition]) -> dict[str, int]:
            ret = {}
            for condition in new_conditions:
                if condition["component"] not in ret:
                    ret[condition["component"]] = 0
                ret[condition["component"]] += 1
            return ret

        new_rules = self.build_new_rules()
        new_rules = self.compress_rules(new_rules)
        for rule, conditions in new_rules.items():
            counts = count_new_condition_per_component(conditions)
            for condition in conditions:
                manifest = self.raw_data[condition["component"]]["manifest"]
                if counts[condition["component"]] == 1 and "weblog" not in condition:
                    manifest[rule] = str(condition["declaration"])
                    self.write_comment(manifest, rule, "Created by easy win activation script", "inline")
                    continue

                if rule not in manifest:
                    manifest[rule] = []
                    self.write_comment(manifest, rule, "Created by easy win activation script", "inline")
                condition_dict = self.serialize_condition(condition)
                if isinstance(manifest[rule], str):
                    if "excluded_component_version" in self.manifest.data:
                        manifest[rule] = [
                            {"weblog_declaration": {"*": manifest.rules[rule]["excluded_component_version"]}}
                        ]
                    else:
                        manifest[rule] = [ManifestEditor.serialize_condition(self.manifest.data[rule][0])]
                manifest[rule].append(condition_dict)
                if isinstance(manifest[rule], CommentedSeq) and len(manifest[rule]) > 0:
                    last_index = len(manifest[rule]) - 1
                    self.write_comment(manifest[rule], last_index, "Added by easy win activation script", "inline")

    def write_poke(self) -> None:
        for view, contexts in self.poked_views.items():
            raw_data = self.raw_data[view.condition["component"]]["manifest"][view.rule]
            component_version, weblogs = ManifestEditor.compress_pokes(contexts)
            all_weblogs = set(weblogs) == self.weblogs[view.condition["component"]] or "parametric-" in next(
                iter(weblogs)
            )

            if "excluded_component_version" in view.condition:
                # Add comment indicating this entry should be updated to allow the test to run for the relevant weblog
                weblog_list = "all weblogs" if all_weblogs else ", ".join(sorted(weblogs))
                comment_text = f"Easy win for {weblog_list} and version {component_version}"
                manifest_map = self.raw_data[view.condition["component"]]["manifest"]
                self.write_comment(manifest_map, view.rule, comment_text, "inline")
                continue
            if view.is_inline:
                if (
                    view.condition["declaration"] == TestDeclaration.MISSING_FEATURE
                    and not view.condition["declaration"].details
                ):
                    if all_weblogs:
                        self.raw_data[view.condition["component"]]["manifest"][view.rule] = f">={component_version}"
                        manifest_map = self.raw_data[view.condition["component"]]["manifest"]
                        self.write_comment(manifest_map, view.rule, "Modified by easy win activation script", "inline")
                        continue
                    self.raw_data[view.condition["component"]]["manifest"][view.rule] = [
                        {"weblog_declaration": {"*": str(view.condition["declaration"])}}
                    ]
                    manifest_map = self.raw_data[view.condition["component"]]["manifest"]
                    self.write_comment(manifest_map, view.rule, "Modified by easy win activation script", "inline")
                    for weblog in weblogs:
                        self.raw_data[view.condition["component"]]["manifest"][view.rule][0]["weblog_declaration"][
                            weblog
                        ] = f">={component_version}"
                    continue

                self.raw_data[view.condition["component"]]["manifest"][view.rule] = [
                    {
                        "declaration": str(view.condition["declaration"]),
                        "component_version": f"<{component_version}",
                    },
                ]
                manifest_map = self.raw_data[view.condition["component"]]["manifest"]
                self.write_comment(manifest_map, view.rule, "Modified by easy win activation script", "inline")
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
                skip = False
                for weblog in raw_data[view.condition_index]["weblog_declaration"]:
                    if re.match(r"\*\w", weblog):
                        skip = True
                if skip:
                    continue
                weblog_declaration = raw_data[view.condition_index]["weblog_declaration"]
                # Add comments to the individual weblog lines that were modified
                for weblog in weblogs:
                    weblog_declaration[weblog] = f"v{component_version}"
                    # Add comment to the specific weblog key that was modified
                    # weblog_declaration is a dict loaded from YAML, so it should be a CommentedMap
                    if isinstance(weblog_declaration, CommentedMap):
                        self.write_comment(
                            weblog_declaration, weblog, "Modified by easy win activation script", "inline"
                        )

            else:
                # Add comment indicating this entry should be updated to allow the test to run for the relevant weblog
                weblog_list = "all weblogs" if all_weblogs else ", ".join(sorted(weblogs))
                comment_text = f"Easy win for {weblog_list} and version {component_version}"
                manifest_map = self.raw_data[view.condition["component"]]["manifest"]
                self.write_comment(manifest_map, view.rule, comment_text, "inline")
                continue

                # Not currently supported because it would require complicated handling
                # of version ranges
                raw_data[view.condition_index]["excluded_weblog"] = CommentedSeq(
                    view.condition.get("excluded_weblog", []) + weblogs
                )
                raw_data[view.condition_index]["excluded_weblog"].fa.set_flow_style()
                condition_item = raw_data[view.condition_index]
                self.write_comment(
                    condition_item, "excluded_weblog", "Modified by easy win activation script", "inline"
                )
                raw_data.append(
                    {
                        "declaration": str(view.condition["declaration"]),
                        "component_version": f"<{component_version}",
                    }
                )
                if isinstance(raw_data, CommentedSeq) and len(raw_data) > 0:
                    self.write_comment(raw_data, len(raw_data) - 1, "Added by easy win activation script", "inline")

                if not all_weblogs:
                    raw_data[-1]["weblog"] = CommentedSeq(weblogs.copy())
                    raw_data[-1]["weblog"].fa.set_flow_style()

    def write(self, output_dir: Path = Path("manifests/")) -> None:
        self.write_new_rules()
        self.write_poke()
        for component, data in self.raw_data.items():
            file = output_dir.joinpath(f"{component}.yml")
            self.round_trip_parser.dump(data, file)
            final_data = file.read_text()
            final_data = self.unwrap_key_anchors(final_data)
            file.write_text(
                f"# yaml-language-server: $schema=https://raw.githubusercontent.com/DataDog/system-tests/refs/heads/main/utils/manifest/schema.json\n{final_data}"
            )
