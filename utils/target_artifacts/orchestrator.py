from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .models import (
    ArtifactEntry,
    TargetArtifactEnvironment,
    TargetArtifactError,
)

if TYPE_CHECKING:
    from types import ModuleType

MANIFEST_FILENAME = ".target-artifacts-manifest.json"
MANIFEST_VERSION = 1


def stage_target(
    target: str,
    environment: str,
    *,
    repo_root: Path | None = None,
    binaries_dir: Path | None = None,
    process_env: dict[str, str] | None = None,
) -> None:
    root = Path.cwd() if repo_root is None else repo_root
    output_dir = Path(os.environ.get("BINARIES_DIR", "binaries")) if binaries_dir is None else binaries_dir
    output_dir = output_dir if output_dir.is_absolute() else root / output_dir

    env = dict(os.environ if process_env is None else process_env)

    if environment == "custom":
        return
    if environment not in {"dev", "prod"}:
        raise TargetArtifactError(f"Unknown target artifact environment: {environment}")

    target_environment = load_target_environment(root, target, environment)
    resolved_inputs = {
        artifact_resolver.name: artifact_resolver.resolve(env)
        for artifact_resolver in target_environment.artifact_inputs(env)
    }
    entries = target_environment.artifact_entries(resolved_inputs)
    write_artifact_entries(output_dir, target, environment, entries)


def load_target_environment(repo_root: Path, target: str, environment: str) -> TargetArtifactEnvironment:
    module_path = repo_root / "utils" / "build" / "docker" / target / "artifact.py"
    if not module_path.exists():
        raise TargetArtifactError(f"No target artifact module found for '{target}' at {module_path}")

    module = _load_module(module_path, f"system_tests_target_artifacts_{target}")
    class_name = "Dev" if environment == "dev" else "Prod"
    environment_class = getattr(module, class_name, None)
    if environment_class is None:
        raise TargetArtifactError(f"Target artifact module for '{target}' does not define {class_name}")

    instance = environment_class()
    if not isinstance(instance, TargetArtifactEnvironment):
        raise TargetArtifactError(f"{target}.{class_name} does not implement TargetArtifactEnvironment")
    return instance


def write_artifact_entries(
    binaries_dir: Path,
    target: str,
    environment: str,
    entries: tuple[ArtifactEntry, ...],
) -> None:
    manifest = _read_manifest(binaries_dir)
    manifest_entries = _manifest_entries(manifest)
    new_entries = _dedupe_entries(entries)
    owner = {"target": target, "environment": environment}

    for filename in new_entries:
        _validate_filename(filename)
        existing_owner = manifest_entries.get(filename, {}).get("owner")
        path = binaries_dir / filename
        if existing_owner is not None and not _same_target(existing_owner, target):
            owner_target = (
                existing_owner.get("target", "<unknown>") if isinstance(existing_owner, dict) else "<unknown>"
            )
            raise TargetArtifactError(f"Artifact entry '{filename}' is already owned by target '{owner_target}'")
        if path.exists() and existing_owner is None:
            raise TargetArtifactError(f"Refusing to overwrite unowned artifact entry '{filename}'")

    for filename, metadata in list(manifest_entries.items()):
        owner_data = metadata.get("owner")
        if _same_target(owner_data, target) and filename not in new_entries:
            path = binaries_dir / filename
            if path.exists():
                path.unlink()
            del manifest_entries[filename]

    binaries_dir.mkdir(parents=True, exist_ok=True)
    for filename, entry in new_entries.items():
        path = binaries_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry.content, encoding="utf-8")
        manifest_entries[filename] = {
            "owner": owner,
            "sha256": hashlib.sha256(entry.content.encode("utf-8")).hexdigest(),
        }

    manifest["version"] = MANIFEST_VERSION
    manifest["entries"] = dict(sorted(manifest_entries.items()))
    manifest_content = f"{json.dumps(manifest, indent=2, sort_keys=True)}\n"
    (binaries_dir / MANIFEST_FILENAME).write_text(manifest_content, encoding="utf-8")


def _load_module(module_path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise TargetArtifactError(f"Unable to import target artifact module at {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_manifest(binaries_dir: Path) -> dict[str, Any]:
    path = binaries_dir / MANIFEST_FILENAME
    if not path.exists():
        return {"version": MANIFEST_VERSION, "entries": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TargetArtifactError(f"Artifact manifest {path} is not an object")
    if payload.get("version") != MANIFEST_VERSION:
        raise TargetArtifactError(f"Unsupported artifact manifest version in {path}")
    return payload


def _manifest_entries(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = manifest.get("entries")
    if not isinstance(entries, dict):
        raise TargetArtifactError("Artifact manifest entries must be an object")
    return {str(name): _metadata(metadata) for name, metadata in entries.items()}


def _metadata(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TargetArtifactError("Artifact manifest entry metadata must be an object")
    return value


def _dedupe_entries(entries: tuple[ArtifactEntry, ...]) -> dict[str, ArtifactEntry]:
    result: dict[str, ArtifactEntry] = {}
    for entry in entries:
        if entry.filename in result:
            raise TargetArtifactError(f"Duplicate artifact entry '{entry.filename}'")
        result[entry.filename] = entry
    return result


def _validate_filename(filename: str) -> None:
    path = Path(filename)
    if path.is_absolute() or ".." in path.parts or filename == MANIFEST_FILENAME:
        raise TargetArtifactError(f"Invalid artifact entry filename '{filename}'")


def _same_target(owner: object, target: str) -> bool:
    return isinstance(owner, dict) and owner.get("target") == target
