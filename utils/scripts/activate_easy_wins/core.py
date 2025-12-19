from __future__ import annotations


from functools import reduce
from typing import TYPE_CHECKING


from utils.scripts.activate_easy_wins.test_artifact import ActivationStatus, TestData

if TYPE_CHECKING:
    from collections.abc import Iterable
    from .types import Context
    from utils.scripts.activate_easy_wins.manifest_editor import ManifestEditor


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


def update_manifest(manifest_editor: ManifestEditor, test_data: dict[Context, TestData]) -> dict[str, int]:
    def get_activation(
        _: object, path: tuple[str], children: Iterable, value: ActivationStatus = ActivationStatus.NONE
    ):
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

    tests_per_language: dict[str, int] = {}
    for context, (nodes, trie) in test_data.items():
        manifest_editor.set_context(context)
        if context.library not in tests_per_language:
            tests_per_language[context.library] = 0
        for node in nodes:
            rules = manifest_editor.get_matches(node)
            tests_per_language[context.library] += 1 if rules else 0
            for rule in rules:
                manifest_editor.poke(rule)
                manifest_editor.add_rules(
                    tups_to_rule(trie.traverse(get_deactivation, rule.rule.replace("::", "/"))), rule
                )
    return tests_per_language


def print_activation_report(tests_per_language: dict[str, int]) -> None:
    """Print a report showing the number of tests activated per language"""
    if not tests_per_language:
        print("No tests were activated.")
        return

    print("\n" + "=" * 50)
    print("Test Activation Report")
    print("=" * 50)
    print(f"{'Language':<20} {'Tests Activated':>15}")
    print("-" * 50)

    total = 0
    for language in sorted(tests_per_language.keys()):
        count = tests_per_language[language]
        total += count
        print(f"{language:<20} {count:>15}")

    print("-" * 50)
    print(f"{'Total':<20} {total:>15}")
    print("=" * 50 + "\n")
