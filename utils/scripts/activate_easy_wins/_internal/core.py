from __future__ import annotations

import contextlib
from functools import reduce
from pathlib import Path
from typing import TYPE_CHECKING

import yaml


from .logger import ActivationLogger
from .test_artifact import ActivationStatus, TestData

if TYPE_CHECKING:
    from collections.abc import Iterable
    from .types import Context
    from .manifest_editor import ManifestEditor


def update_manifest(
    manifest_editor: ManifestEditor, test_data: dict[Context, TestData], skipped_nodes: dict | None = None
) -> ActivationLogger:

    def tup_to_rule(tup: tuple[str, ...]) -> str:
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

    def get_deactivation(
        _: object, path: tuple[str], children: Iterable, value: ActivationStatus = ActivationStatus.NONE
    ):
        if value == ActivationStatus.XFAIL:
            return [path]
        if value == ActivationStatus.NONE:
            return reduce(lambda x, y: x + y, list(children), [])
        return []

    logger = ActivationLogger()
    skipped_nodes = skipped_nodes or {}

    for context, test_data_item in test_data.items():
        nodes, trie = test_data_item.xpass_nodes, test_data_item.trie
        nodeid_to_owners = test_data_item.nodeid_to_owners
        manifest_editor.set_context(context)
        logger.init_language(context.library)
        for node in nodes:
            if node in skipped_nodes.get(context.library, []) + skipped_nodes.get("*", []):
                continue
            views = manifest_editor.get_matches(node)
            if views:
                logger.record_activation(
                    context.library, node, nodeid_to_owners.get(node, set()), [v.rule for v in views]
                )
                for view in views:
                    manifest_editor.poke(view)
                    with contextlib.suppress(KeyError):
                        manifest_editor.add_rules(
                            tups_to_rule(trie.traverse(get_deactivation, view.rule.replace("::", "/"))), view
                        )
            else:
                logger.record_no_rule()

    return logger
