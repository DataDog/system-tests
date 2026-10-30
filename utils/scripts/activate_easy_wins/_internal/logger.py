from __future__ import annotations


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


class ActivationLogger:
    """Encapsulates all logging state and print methods for the activation process."""

    def __init__(self) -> None:
        self.tests_per_language: dict[str, int] = {}
        self.unique_tests_per_language: dict[str, set[str]] = {}
        self.modified_rules_by_level: dict[str, int] = {"dir": 0, "file": 0, "class": 0, "function": 0}
        self._modified_rules_set: set[str] = set()
        self.rule_to_tests: dict[str, set[str]] = {}
        self.tests_without_rules: int = 0
        self.tests_with_rules: int = 0
        self.activations_per_owner: dict[str, int] = {}

    @property
    def total_tests_activated(self) -> int:
        return sum(self.tests_per_language.values())

    @property
    def unique_tests_per_language_count(self) -> dict[str, int]:
        return {lang: len(tests) for lang, tests in self.unique_tests_per_language.items()}

    @property
    def total_unique_tests(self) -> int:
        return sum(self.unique_tests_per_language_count.values())

    @property
    def total_modified_rules(self) -> int:
        return sum(self.modified_rules_by_level.values())

    def init_language(self, library: str) -> None:
        if library not in self.tests_per_language:
            self.tests_per_language[library] = 0
            self.unique_tests_per_language[library] = set()

    def record_activation(self, library: str, node: str, owners: set[str], rules: list[str]) -> None:
        self.tests_with_rules += 1
        self.tests_per_language[library] += 1
        self.unique_tests_per_language[library].add(node)
        for owner in owners:
            self.activations_per_owner[owner] = self.activations_per_owner.get(owner, 0) + 1
        for rule_str in rules:
            if rule_str not in self.rule_to_tests:
                self.rule_to_tests[rule_str] = set()
            self.rule_to_tests[rule_str].add(node)
            if rule_str not in self._modified_rules_set:
                self._modified_rules_set.add(rule_str)
                self.modified_rules_by_level[_get_rule_level(rule_str)] += 1

    def record_no_rule(self) -> None:
        self.tests_without_rules += 1

    def print_top_rules(self) -> None:
        if not self.rule_to_tests:
            return
        sorted_rules = sorted(self.rule_to_tests.items(), key=lambda x: len(x[1]), reverse=True)
        print("\nTop 10 rules by number of unique matching tests:")
        print("-" * 80)
        for rule, matching_tests in sorted_rules[:10]:
            print(f"{rule:<60} {len(matching_tests):>5} unique tests")
        print("-" * 80)
        print()

    def print_activation_report(self) -> None:
        if not self.tests_per_language:
            print("No tests were activated.")
            return

        unique_counts = self.unique_tests_per_language_count
        print("\n" + "=" * 70)
        print("Test Activation Report")
        print("=" * 70)
        print("(Shows test activations = test nodeid + context combinations)")
        print(f"{'Language':<20} {'Activations':>15} {'Unique Tests':>15}")
        print("-" * 70)

        total_activations = 0
        total_unique = 0
        for language in sorted(self.tests_per_language.keys()):
            activations = self.tests_per_language[language]
            unique = unique_counts.get(language, 0)
            total_activations += activations
            total_unique += unique
            print(f"{language:<20} {activations:>15} {unique:>15}")

        print("-" * 70)
        print(f"{'Total':<20} {total_activations:>15} {total_unique:>15}")
        print("=" * 70 + "\n")

    def print_detailed_rules_report(self, created_rules_count: int) -> None:
        print("=" * 50)
        print("Detailed Rules Report")
        print("=" * 50)
        print("(One rule can match multiple tests - e.g., a class rule matches all test methods)")
        print()

        print("Rules Modified by Level:")
        print("-" * 50)
        print(f"{'Level':<15} {'Count':>15}")
        print("-" * 50)

        total_modified = self.total_modified_rules
        for level in ["dir", "file", "class", "function"]:
            count = self.modified_rules_by_level.get(level, 0)
            print(f"{level:<15} {count:>15}")

        print("-" * 50)
        print(f"{'Total Modified':<15} {total_modified:>15}")

        print("\nRules Created:")
        print("-" * 50)
        print(f"{'Total Created':<15} {created_rules_count:>15}")

        if total_modified > 0:
            total_unique = self.total_unique_tests
            avg_unique_tests_per_rule = total_unique / total_modified
            print("\nSummary:")
            print("-" * 50)
            print(f"{'Total Test Activations':<30} {self.total_tests_activated:>10}")
            print(f"{'Total Unique Tests':<30} {total_unique:>10}")
            print(f"{'Total Rules Modified':<30} {total_modified:>10}")
            print(f"{'Avg Unique Tests per Rule':<30} {avg_unique_tests_per_rule:>10.1f}")
            if self.tests_without_rules > 0:
                print(f"{'Tests Without Matching Rules':<30} {self.tests_without_rules:>10}")

        if self.activations_per_owner:
            sorted_owners = sorted(self.activations_per_owner.items(), key=lambda x: x[1], reverse=True)
            col = max(len(o) for o, _ in sorted_owners[:5]) + 2
            w = col + 16
            print("\nTop 5 Code Owners by Activations:")
            print("-" * w)
            print(f"{'Code Owner':<{col}} {'Activations':>15}")
            print("-" * w)
            for owner, count in sorted_owners[:5]:
                print(f"{owner:<{col}} {count:>15}")
            print("=" * w + "\n")

    @staticmethod
    def print_split_co_report(results: dict[str, int]) -> None:
        col = max((len(k) for k in results), default=10) + 2
        w = col + 16
        print("\n" + "=" * w)
        print("Activations per Code Owner")
        print("=" * w)
        print(f"{'Code Owner':<{col}} {'Activations':>15}")
        print("-" * w)
        total = 0
        for owner in sorted(results, key=lambda k: results[k], reverse=True):
            print(f"{owner:<{col}} {results[owner]:>15}")
            total += results[owner]
        print("-" * w)
        print(f"{'Total':<{col}} {total:>15}")
        print("=" * w + "\n")
