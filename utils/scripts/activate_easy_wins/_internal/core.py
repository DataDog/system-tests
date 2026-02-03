from __future__ import annotations


from functools import reduce
from pathlib import Path
from typing import TYPE_CHECKING


from .test_artifact import ActivationStatus, TestData

if TYPE_CHECKING:
    from collections.abc import Iterable
    from .types import Context
    from .manifest_editor import ManifestEditor


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


def _get_rule_level(rule: str) -> str:
    """Determine the level of a rule: dir, file, class, or function"""
    class_len = 2
    function_len = 3
    if "::" in rule:
        parts = rule.split("::")
        if len(parts) == class_len:
            return "class"
        if len(parts) >= function_len:
            return "function"
    if rule.endswith(".py"):
        return "file"
    return "dir"


def update_manifest(
    manifest_editor: ManifestEditor, test_data: dict[Context, TestData]
) -> tuple[dict[str, int], dict[str, int], int, int, dict[str, int], dict[str, int]]:
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
    modified_rules_by_level: dict[str, int] = {"dir": 0, "file": 0, "class": 0, "function": 0}
    modified_rules_set: set[str] = set()
    tests_without_rules: int = 0
    tests_with_rules: int = 0
    rule_to_tests: dict[str, set[str]] = {}  # Track unique test nodeids per rule
    unique_tests_per_language: dict[str, set[str]] = {}  # Track unique test nodeids per language
    activations_per_owner: dict[str, int] = {}  # Track activations per code owner
    skipped_nodes = set(Path("utils/scripts/activate_easy_wins/skip.csv").read_text().splitlines())

    for context, test_data_item in test_data.items():
        nodes, trie = test_data_item.xpass_nodes, test_data_item.trie
        nodeid_to_owners = test_data_item.nodeid_to_owners
        manifest_editor.set_context(context)
        if context.library not in tests_per_language:
            tests_per_language[context.library] = 0
            unique_tests_per_language[context.library] = set()
        for node in nodes:
            if node in skipped_nodes:
                continue
            views = manifest_editor.get_matches(node)
            if views:
                tests_with_rules += 1
                tests_per_language[context.library] += 1
                unique_tests_per_language[context.library].add(node)
                # Track activations per code owner
                test_owners = nodeid_to_owners.get(node, set())
                for owner in test_owners:
                    activations_per_owner[owner] = activations_per_owner.get(owner, 0) + 1
                for view in views:
                    rule_str = view.rule
                    if rule_str not in rule_to_tests:
                        rule_to_tests[rule_str] = set()
                    rule_to_tests[rule_str].add(node)  # Use set to track unique test nodeids
                    if rule_str not in modified_rules_set:
                        modified_rules_set.add(rule_str)
                        level = _get_rule_level(rule_str)
                        modified_rules_by_level[level] += 1
                    manifest_editor.poke(view)
                    manifest_editor.add_rules(
                        tups_to_rule(trie.traverse(get_deactivation, view.rule.replace("::", "/"))), view
                    )
            else:
                tests_without_rules += 1

    # Debug: Print top rules by number of unique matching tests
    if rule_to_tests:
        sorted_rules = sorted(rule_to_tests.items(), key=lambda x: len(x[1]), reverse=True)
        print("\nTop 10 rules by number of unique matching tests:")
        print("-" * 80)
        for rule, matching_tests in sorted_rules[:10]:
            print(f"{rule:<60} {len(matching_tests):>5} unique tests")
        print("-" * 80)
        print()

    # Count created rules (rules in added_rules are new rules to be created)
    created_rules_count = len(manifest_editor.added_rules)

    # Convert unique tests sets to counts
    unique_tests_per_language_count: dict[str, int] = {
        lang: len(tests) for lang, tests in unique_tests_per_language.items()
    }

    return (
        tests_per_language,
        modified_rules_by_level,
        created_rules_count,
        tests_without_rules,
        unique_tests_per_language_count,
        activations_per_owner,
    )


def print_activation_report(tests_per_language: dict[str, int], unique_tests_per_language: dict[str, int]) -> None:
    """Print a report showing the number of tests activated per language"""
    if not tests_per_language:
        print("No tests were activated.")
        return

    print("\n" + "=" * 70)
    print("Test Activation Report")
    print("=" * 70)
    print("(Shows test activations = test nodeid + context combinations)")
    print(f"{'Language':<20} {'Activations':>15} {'Unique Tests':>15}")
    print("-" * 70)

    total_activations = 0
    total_unique = 0
    for language in sorted(tests_per_language.keys()):
        activations = tests_per_language[language]
        unique = unique_tests_per_language.get(language, 0)
        total_activations += activations
        total_unique += unique
        print(f"{language:<20} {activations:>15} {unique:>15}")

    print("-" * 70)
    print(f"{'Total':<20} {total_activations:>15} {total_unique:>15}")
    print("=" * 70 + "\n")


def print_detailed_rules_report(
    modified_rules_by_level: dict[str, int],
    created_rules_count: int,
    total_tests_activated: int,
    total_unique_tests: int,
    tests_without_rules: int = 0,
    activations_per_owner: dict[str, int] | None = None,
) -> None:
    """Print a detailed report showing rules modified by level and rules created"""
    print("=" * 50)
    print("Detailed Rules Report")
    print("=" * 50)
    print("(One rule can match multiple tests - e.g., a class rule matches all test methods)")
    print()

    # Rules modified section
    print("Rules Modified by Level:")
    print("-" * 50)
    print(f"{'Level':<15} {'Count':>15}")
    print("-" * 50)

    total_modified = 0
    for level in ["dir", "file", "class", "function"]:
        count = modified_rules_by_level.get(level, 0)
        total_modified += count
        print(f"{level:<15} {count:>15}")

    print("-" * 50)
    print(f"{'Total Modified':<15} {total_modified:>15}")

    # Rules created section
    print("\nRules Created:")
    print("-" * 50)
    print(f"{'Total Created':<15} {created_rules_count:>15}")

    # Summary
    if total_modified > 0:
        avg_unique_tests_per_rule = total_unique_tests / total_modified
        print("\nSummary:")
        print("-" * 50)
        print(f"{'Total Test Activations':<30} {total_tests_activated:>10}")
        print(f"{'Total Unique Tests':<30} {total_unique_tests:>10}")
        print(f"{'Total Rules Modified':<30} {total_modified:>10}")
        print(f"{'Avg Unique Tests per Rule':<30} {avg_unique_tests_per_rule:>10.1f}")
        if tests_without_rules > 0:
            print(f"{'Tests Without Matching Rules':<30} {tests_without_rules:>10}")

    # Code owner summary
    if activations_per_owner:
        print("\nTop 5 Code Owners by Activations:")
        print("-" * 50)
        print(f"{'Code Owner':<40} {'Activations':>10}")
        print("-" * 50)
        sorted_owners = sorted(activations_per_owner.items(), key=lambda x: x[1], reverse=True)
        for owner, count in sorted_owners[:5]:
            print(f"{owner:<40} {count:>10}")
        print("=" * 50 + "\n")
