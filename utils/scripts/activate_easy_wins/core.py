from __future__ import annotations


from functools import reduce
from typing import TYPE_CHECKING, Iterable

from semantic_version.base import functools

from utils.scripts.activate_easy_wins.test_artifact import ActivationStatus, TestData
from utils.scripts.activate_easy_wins.utils import get_impacted_nodeids

if TYPE_CHECKING:
    from .types import Context
    from utils.scripts.activate_easy_wins.manifest_editor import ManifestEditor


def tup_to_rule(tup: tuple[str]) -> str:
    rule = tup[0]
    sep = "/"
    for element in tup[1:]:
        rule += f"{sep}{element}"
        if element.endswith(".py"):
            sep = "::"
    return rule


def tups_to_rule(tups: list[tuple[str]]) -> list[str]:
    ret = []
    for tup in tups:
        ret.append(tup_to_rule(tup))
    return ret


def update_manifest(manifest_editor: ManifestEditor, test_data: dict[Context, TestData]) -> None:
    def get_activation(path_conv, path, children, value=ActivationStatus.NONE):
        if value == ActivationStatus.XPASS:
            return [path]
        if value == ActivationStatus.NONE:
            return reduce(lambda x, y: x + y, list(children), [])
        return []

    def get_deactivation(
        _: object, path: tuple[str], children: Iterable, value: ActivationStatus = ActivationStatus.NONE
    ):
        if value == ActivationStatus.XFAIL:
            return [path]
        if value == ActivationStatus.NONE:
            return reduce(lambda x, y: x + y, list(children), [])
        return []

    for context, (nodes, trie) in test_data.items():
        manifest_editor.set_context(context)
        for node in nodes:
            rules = manifest_editor.get_matches(node)
            for rule in rules:
                manifest_editor.poke(rule)
                manifest_editor.add_rules(
                    tups_to_rule(trie.traverse(get_deactivation, rule.rule.replace("::", "/"))), rule
                )

    # for view, contexts in manifest_editor.poked_views.items():
    #     print(view.rule)
    #     for context in contexts:
    #         print(context)
    # for rule, parents in manifest_editor.added_rule.items():
    #     print(rule)
    #     for parent in parents:
    #         print(parent.condition)

    # for context, nodeids in test_data.items():
    #     manifest_editor.set_context(context)
    #
    #     for nodeid in nodeids:
    #         rules = manifest_editor.get_matches(nodeid)
    #
    #         for rule in rules:
    #             if rule.clause_key == "*":
    #                 manifest_editor.update(rule, f"v{context.library_version}", append_key=context.variant)
    #             else:
    #                 manifest_editor.update(rule, f"v{context.library_version}")
    #
    #             print(rule.rule.replace("::", "/"))
    #             if test_data.xfail[context].has_subtrie(rule.rule.replace("::", "/")):
    #                 print(test_data.xfail[context].items(prefix=rule.rule.replace("::", "/")))
    #
    # for new_rules in impacted_nodeids.values():
    #     for new_rule in new_rules:
    #         if manifest_editor.contains(new_rule):
    #             manifest_editor.add_condition(
    #                 new_rule, {"weblog_declaration": {context.variant: context.library_version}}
    #             )
    #         else:
    #             manifest_editor.add_rule(new_rule)
