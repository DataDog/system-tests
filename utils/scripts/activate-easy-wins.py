from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import zipfile
from enum import Enum
from pathlib import Path
from typing import Any
from dataclasses import dataclass
from utils._context.component_version import Version
from utils.get_declaration import get_rules, match_rule, is_terminal, get_all_nodeids, update_rule
from utils._decorators import CustomSpec
from utils._logger import get_logger
from manifests.parser.core import _load_file

import requests
import ruamel.yaml
ruamel.yaml.emitter.Emitter.MAX_SIMPLE_KEY_LENGTH = 1000
from tqdm import tqdm


class ChangeSummary:
    """Summary of changes made to a manifest. Tracks changes incrementally like a logger."""
    
    def __init__(self) -> None:
        self.logger = get_logger(__name__)
        self.updated_activation_rules: dict[str, tuple[Any, Any]] = {}  # rule -> (old_value, new_value) - rules that were modified
        self.newly_activated_tests: dict[str, Any] = {}  # test -> new_value - tests being activated for the first time
        self.maintained_deactivation_rules: dict[str, Any] = {}  # test -> deactivation_value - tests kept deactivated (not easy wins)
    
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

@dataclass
class Context:
    library: str
    library_version: Version
    variant: str

    @staticmethod
    def create(library: str, library_version: str, variant: str) -> Context|None:
        if library not in LIBRARIES or not library_version or not (library_version := Version(library_version)):
            return None
        return Context(library, library_version, variant)


    def __hash__(self):
        return hash((self.library, str(self.library_version), self.variant))




ARTIFACT_URL = (
    "https://api.github.com/repos/DataDog/system-tests-dashboard/actions/workflows/nightly.yml/runs?per_page=1"
)


def pull_artifact(url: str, token: str, path_root: str, path_data_root: str) -> None:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "python-requests",
    }

    # Get workflow runs
    with requests.get(url, headers=headers, timeout=60) as resp_runs:
        resp_runs.raise_for_status()
        runs_data = resp_runs.json()

    download_url = None
    page = 0
    print(f"CI workflow URL: {runs_data['workflow_runs'][0]['html_url']}")
    while not download_url:
        page += 1
        artifacts_url = runs_data["workflow_runs"][0]["artifacts_url"] + f"?page={page}"
        with requests.get(artifacts_url, headers=headers, timeout=60) as resp_artifacts:
            resp_artifacts.raise_for_status()
            artifacts_data = resp_artifacts.json()

        # Download the first artifact
        for artifact in artifacts_data["artifacts"]:
            if artifact["name"] == "test-report":
                download_url = artifact["archive_download_url"]

        # If we've checked all pages and found no test-report artifact, error
        if not download_url and len(artifacts_data["artifacts"]) == 0:
            raise RuntimeError("test-report not found in the last nightly run")

    with requests.get(download_url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        total_size = int(r.headers.get("content-length", 0))

        with (
            open(f"{path_root}/data.zip", "wb") as f,
            tqdm(total=total_size, unit="B", unit_scale=True, desc="Downloading artifact") as pbar,
        ):
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

    # Extract the downloaded zip file
    with zipfile.ZipFile(f"{path_root}/data.zip") as z:
        z.extractall(path_data_root)

def parse_artifact_data(
    path_data_opt: str, libraries: list[str]
) -> dict[Context, list[str]]:
    test_data: dict[Context, list[str]] = {}

    for directory in os.listdir(path_data_opt):
        if "_dev_" in directory:
            continue

        for scenario in os.listdir(f"{path_data_opt}/{directory}"):
            try:
                with open(f"{path_data_opt}/{directory}/{scenario}/report.json", encoding="utf-8") as file:
                    scenario_data = json.load(file)
            except FileNotFoundError:
                continue

            context = Context.create(scenario_data["context"].get("library_name"), scenario_data["context"].get("library"), scenario_data["context"].get("weblog_variant"))

            if not context or context.library not in libraries:
                break

            if context not in test_data:
                test_data[context] = []

            for test in scenario_data["tests"]:
                if test["outcome"] == "xpassed":
                    test_data[context].append(test["nodeid"])

    return test_data


def parse_manifest(library: str, path_root: str, yaml: ruamel.yaml.YAML) -> ruamel.yaml.CommentedMap:  # type: ignore[type-arg]
    with open(f"{path_root}/manifests/{library}.yml", encoding="utf-8") as file:
        return yaml.load(file)


def write_manifest(manifest: ruamel.yaml.CommentedMap, outfile_path: str, yaml: ruamel.yaml.YAML) -> None:  # type: ignore[type-arg]
    with open(outfile_path, "w", encoding="utf8") as outfile:
        yaml.dump(manifest, outfile)


def update_manifest(
    library: str,
    manifest: ruamel.yaml.CommentedMap,
    test_data: dict[Context, list[str]],
    excluded_owners: set[str],
) -> ChangeSummary:
    # Store original manifest state for comparison
    original_manifest = copy.deepcopy(manifest["manifest"])
    
    # Initialize change summary at the beginning (like a logger)
    summary = ChangeSummary()
    
    updates = {}
    parsed_manifest = _load_file(f"manifests/{library}.yml", library)
    for context, nodeids in test_data.items():
        if context.library != library:
            continue
        rules = get_rules(context.library, context.library_version, context.variant)
        for nodeid in nodeids:
            for rule, declarations in rules.items():
                if not match_rule(rule, nodeid):
                    continue
                if "flaky" in declarations or "irrelevant" in declarations: # wrong TODO
                    continue
                if rule not in updates:
                    updates[rule] = set()
                updates[rule].add((nodeid, context))

    additions = {}
    updated = {}
    for rule, targets in updates.items():
        nodeids = set([target[0][:target[0].find("[")%(len(target[0]) + 1)] for target in targets])
        contexts = set([target[1] for target in targets])
        updated[rule] = parsed_manifest[rule]
        update_rule(updated[rule], contexts, manifest["manifest"][rule])
        
        if is_terminal(rule):
            continue
        all_targets = set(get_all_nodeids(rule))
        if all_targets == nodeids:
            continue
        
        for nodeid in all_targets - nodeids:
            new_val = manifest["manifest"][rule]
            if isinstance(new_val, str):
                new_val = [new_val]
            else:
                # new_val = copy.deepcopy(manifest["manifest"][rule])
                new_val = manifest["manifest"][rule]
            if nodeid not in additions:
                additions[nodeid] = new_val
            else:
                additions[nodeid] += new_val

        # Log newly activated tests as they're added
        for nodeid in nodeids:
            old_nodeid_value = original_manifest.get(nodeid)
            new_nodeid_value = f">={max(context.library_version for context in contexts)}"
            manifest["manifest"][nodeid] = new_nodeid_value
            
            # Track activation: new test or updated existing test
            summary.log_activation_change(nodeid, old_nodeid_value, new_nodeid_value, original_manifest)
        
    for k, vs in additions.items():
        for v in vs:
            if isinstance(v, str):
                additions[k] = v

    # Log additions as they're applied to manifest
    for k, v in additions.items():
        if isinstance(v, str) and isinstance(manifest["manifest"].get(k), str):
            continue
        if isinstance(v, str):
            manifest["manifest"][k] = v
            summary.log_addition_change(k, v, original_manifest)
            continue
        if isinstance(manifest["manifest"].get(k), ruamel.yaml.comments.CommentedSeq):
            manifest["manifest"][k].append(v)
            new_value = manifest["manifest"][k]
            summary.log_addition_change(k, v, original_manifest, final_value=new_value)
            continue
        manifest["manifest"][k] = v
        summary.log_addition_change(k, v, original_manifest)
    
    # Log rule updates as they're written back to manifest
    for k, v in updated.items():
        old_value = original_manifest.get(k)
        manifest["manifest"][k] = []
        for condition in v:
            manifest["manifest"][k].append({})
            for clause_name, clause_val in condition.items():
                if clause_name == "library":
                    continue
                if isinstance(clause_val, CustomSpec):
                    clause_val = str(clause_val)
                if isinstance(clause_val, list):
                    clause_val = ruamel.yaml.CommentedSeq(clause_val)
                    clause_val.fa.set_flow_style()
                manifest["manifest"][k][-1][clause_name] = clause_val
        
        # Log the rule update after writing back
        new_value = manifest["manifest"][k]
        summary.log_updated_rule(k, old_value, new_value)
    
    return summary


def get_environ() -> dict[str, str]:
    environ = {**os.environ}

    try:
        with open(".env", "r", encoding="utf-8") as f:
            lines = [line.replace("export ", "").strip().split("=") for line in f if line.strip()]
            environ = {**environ, **dict(lines)}
    except FileNotFoundError:
        pass

    return environ


def main() -> None:
    environ = get_environ()
    parser = argparse.ArgumentParser(description="Activate easy wins in system tests")
    parser.add_argument(
        "--libraries",
        nargs="*",
        choices=LIBRARIES,
        default=LIBRARIES,
        help="Libraries to update (default: all libraries)",
    )
    parser.add_argument("--no-download", action="store_true", help="Skip downloading test data")
    parser.add_argument("--data-path", type=str, help="Custom path to store test data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without writing to files")
    parser.add_argument("--summary-only", action="store_true", help="Show only the final summary")
    parser.add_argument("--exclude", nargs="*", default=[], help="List of owners to exclude from activation")

    args = parser.parse_args()

    yaml = ruamel.yaml.YAML()
    yaml.explicit_start = True
    yaml.width = 10000
    yaml.comment_column = 10000
    yaml.allow_unicode = True
    yaml.default_flow_style = False
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    path_root = str(Path(__file__).parents[2])
    path_data_root = args.data_path if args.data_path else f"{path_root}/data"
    path_data_opt = path_data_root

    if not args.no_download:
        print("Pulling test results")
        token = environ["GITHUB_TOKEN"]  # expects your GitHub token in env var
        pull_artifact(ARTIFACT_URL, token, path_root, path_data_root)

    print("Parsing test results")
    test_data = parse_artifact_data(path_data_opt, args.libraries)

    if args.dry_run and not args.summary_only:
        print("🔍 DRY RUN MODE - No files will be modified\n")

    excluded_owners = set(args.exclude)
    all_summaries: dict[str, ChangeSummary] = {}

    for library in args.libraries:
        manifest = parse_manifest(library, path_root, yaml)
        summary = update_manifest(library, manifest, test_data, excluded_owners)
        all_summaries[library] = summary

        if not args.summary_only:
            action = "Analyzing" if args.dry_run else "Processing"
            print(f"📋 {action} {library.upper()}...")

        if not args.dry_run:
            write_manifest(manifest, f"{path_root}/manifests/{library}.yml", yaml)

    # Display comprehensive summary
    print("\n" + "="*80)
    if args.dry_run:
        print("🔍 DRY RUN SUMMARY")
    else:
        print("🎉 CHANGE SUMMARY")
    print("="*80)
    
    total_updated = sum(len(s.updated_activation_rules) for s in all_summaries.values())
    total_newly_activated = sum(len(s.newly_activated_tests) for s in all_summaries.values())
    total_maintained_deactivations = sum(len(s.maintained_deactivation_rules) for s in all_summaries.values())
    
    print(f"\n📊 Overall Statistics:")
    print(f"   • Updated activation rules: {total_updated}")
    print(f"   • Newly activated tests: {total_newly_activated}")
    print(f"   • Maintained deactivation rules: {total_maintained_deactivations}")
    print(f"   • Total changes: {total_updated + total_newly_activated + total_maintained_deactivations}")
    
    # Per-library breakdown
    print(f"\n📚 Per-Library Breakdown:")
    for library, summary in all_summaries.items():
        lib_total = (
            len(summary.updated_activation_rules) +
            len(summary.newly_activated_tests) +
            len(summary.maintained_deactivation_rules)
        )
        if lib_total > 0 or not args.summary_only:
            print(f"\n   {library.upper()}:")
            if summary.updated_activation_rules:
                print(f"      • Updated activation rules: {len(summary.updated_activation_rules)}")
                if not args.summary_only:
                    for rule, (old_val, new_val) in list(summary.updated_activation_rules.items())[:5]:
                        print(f"        - {rule}")
                        print(f"          Old: {_format_value(old_val)}")
                        print(f"          New: {_format_value(new_val)}")
                    if len(summary.updated_activation_rules) > 5:
                        print(f"        ... and {len(summary.updated_activation_rules) - 5} more")
            if summary.newly_activated_tests:
                print(f"      • Newly activated tests: {len(summary.newly_activated_tests)}")
                if not args.summary_only:
                    for test, val in list(summary.newly_activated_tests.items())[:5]:
                        print(f"        - {test}: {_format_value(val)}")
                    if len(summary.newly_activated_tests) > 5:
                        print(f"        ... and {len(summary.newly_activated_tests) - 5} more")
            if summary.maintained_deactivation_rules:
                print(f"      • Maintained deactivation rules: {len(summary.maintained_deactivation_rules)}")
                if not args.summary_only:
                    for test, val in list(summary.maintained_deactivation_rules.items())[:5]:
                        print(f"        - {test}: {_format_value(val)}")
                    if len(summary.maintained_deactivation_rules) > 5:
                        print(f"        ... and {len(summary.maintained_deactivation_rules) - 5} more")
            if lib_total == 0 and not args.summary_only:
                print(f"      • No changes")
    
    print("\n" + "="*80)


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

    # Exit with non-zero status if no updates were made (or would be made in dry-run)
    if total_updates == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
