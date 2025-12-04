from __future__ import annotations

import os
from typing import Any
from utils._logger import get_logger

import ruamel.yaml

ruamel.yaml.emitter.Emitter.MAX_SIMPLE_KEY_LENGTH = 1000
from tqdm import tqdm


class ChangeSummary:
    """Summary of changes made to a manifest. Tracks changes incrementally like a logger."""

    def __init__(self) -> None:
        self.logger = get_logger(__name__)
        self.updated_activation_rules: dict[
            str, tuple[Any, Any]
        ] = {}  # rule -> (old_value, new_value) - rules that were modified
        self.newly_activated_tests: dict[str, Any] = {}  # test -> new_value - tests being activated for the first time
        self.maintained_deactivation_rules: dict[
            str, Any
        ] = {}  # test -> deactivation_value - tests kept deactivated (not easy wins)

    def log_newly_activated_test(self, nodeid: str, new_value: Any) -> None:
        """Log a test that is being activated for the first time."""
        if nodeid not in self.newly_activated_tests:
            self.newly_activated_tests[nodeid] = new_value
            self.logger.debug("Newly activated test: %s -> %s", nodeid, _format_value(new_value))

    def log_updated_rule(self, rule: str, old_value: Any, new_value: Any) -> None:
        """Log a rule that was updated (existed before and was changed)."""
        if old_value != new_value and rule not in self.updated_activation_rules:
            self.updated_activation_rules[rule] = (old_value, new_value)
            self.logger.debug(
                "Updated activation rule: %s -> old: %s, new: %s",
                rule,
                _format_value(old_value),
                _format_value(new_value),
            )

    def log_maintained_deactivation(self, nodeid: str, deactivation_value: Any) -> None:
        """Log a deactivation rule that is being maintained (test kept deactivated)."""
        if nodeid not in self.maintained_deactivation_rules:
            self.maintained_deactivation_rules[nodeid] = deactivation_value
            self.logger.debug(
                "Maintained deactivation rule: %s -> %s",
                nodeid,
                _format_value(deactivation_value),
            )

    def log_activation_change(
        self,
        nodeid: str,
        old_value: Any,
        new_value: Any,
        original_manifest: dict[str, Any],
    ) -> None:
        """Log an activation change (new activation or update to existing rule)."""
        if nodeid not in original_manifest:
            self.log_newly_activated_test(nodeid, new_value)
        else:
            self.log_updated_rule(nodeid, old_value, new_value)

    def log_addition_change(
        self,
        nodeid: str,
        addition_value: Any,
        original_manifest: dict[str, Any],
        final_value: Any | None = None,
    ) -> None:
        """Log a change from additions (can be deactivation marker or activation)."""
        old_value = original_manifest.get(nodeid)
        is_deactivation = _is_deactivation_marker(addition_value)
        final_value = final_value if final_value is not None else addition_value

        if is_deactivation:
            if nodeid not in original_manifest:
                self.log_maintained_deactivation(nodeid, final_value)
            elif old_value != final_value:
                self.log_updated_rule(nodeid, old_value, final_value)
        else:
            self.log_activation_change(nodeid, old_value, final_value, original_manifest)


class UnexpectedStatusError(Exception):
    """Raised when an unexpected status is encountered."""


LIBRARIES = [
    # "agent",
    "cpp_httpd",
    # "cpp_nginx",
    "cpp",
    # "dd_apm_inject",
    "dotnet",
    "golang",
    "java",
    # "k8s_cluster_agent",
    "nodejs",
    "php",
    "python_lambda",
    # "python_otel",
    "python",
    "ruby",
    # "rust"
]


ARTIFACT_URL = (
    "https://api.github.com/repos/DataDog/system-tests-dashboard/actions/workflows/nightly.yml/runs?per_page=1"
)


def get_environ() -> dict[str, str]:
    environ = {**os.environ}

    try:
        with open(".env", "r", encoding="utf-8") as f:
            lines = [line.replace("export ", "").strip().split("=") for line in f if line.strip()]
            environ = {**environ, **dict(lines)}
    except FileNotFoundError:
        pass

    return environ


def _is_deactivation_marker(value: Any) -> bool:
    """Check if a manifest value represents a deactivation marker.

    Deactivation markers include: missing_feature, irrelevant, bug, flaky
    """
    if value is None:
        return False

    if isinstance(value, str):
        # String values like "missing_feature (reason)" or "irrelevant (reason)"
        value_lower = value.lower()
        return any(marker in value_lower for marker in ["missing_feature", "irrelevant", "bug", "flaky"])

    if isinstance(value, (list, ruamel.yaml.comments.CommentedSeq)):
        # Check if any condition in the list has a deactivation declaration
        for condition in value:
            if isinstance(condition, dict):
                decl = condition.get("declaration")
                if decl:
                    if isinstance(decl, str):
                        decl_lower = decl.lower()
                        if any(marker in decl_lower for marker in ["missing_feature", "irrelevant", "bug", "flaky"]):
                            return True
                    # Handle CustomSpec or other types
                    decl_str = str(decl).lower()
                    if any(marker in decl_str for marker in ["missing_feature", "irrelevant", "bug", "flaky"]):
                        return True

    # Check if it's a dict with declaration field
    if isinstance(value, dict):
        decl = value.get("declaration")
        if decl:
            decl_str = str(decl).lower()
            return any(marker in decl_str for marker in ["missing_feature", "irrelevant", "bug", "flaky"])

    return False


def _format_value(value: Any) -> str:
    """Format a manifest value for display."""
    if value is None:
        return "None"
    if isinstance(value, str):
        return value
    if isinstance(value, (list, ruamel.yaml.comments.CommentedSeq)):
        if len(value) == 0:
            return "[]"
        if len(value) == 1:
            return str(value[0])
        return f"[{len(value)} conditions]"
    if isinstance(value, dict):
        return f"{{dict with {len(value)} keys}}"
    return str(value)
