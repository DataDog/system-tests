from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def load_duration_manifest(path: Path) -> dict[str, float]:
    if not path.is_file():
        raise FileNotFoundError(f"Duration manifest does not exist: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise ValueError(f"Duration manifest must be a non-empty JSON object: {path}")

    durations: dict[str, float] = {}
    for node_id, duration in data.items():
        if not isinstance(node_id, str):
            raise TypeError(f"Duration manifest contains a non-string node ID: {node_id!r}")
        if not node_id:
            raise ValueError(f"Duration manifest contains an invalid node ID: {node_id!r}")
        if not isinstance(duration, (int, float)) or isinstance(duration, bool):
            raise TypeError(f"Duration manifest contains a non-numeric duration for {node_id!r}: {duration!r}")
        if duration < 0:
            raise ValueError(f"Duration manifest contains an invalid duration for {node_id!r}: {duration!r}")
        durations[node_id] = float(duration)
    return durations


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def membership_hash(node_ids: list[str]) -> str:
    payload = "".join(f"{node_id}\n" for node_id in sorted(node_ids)).encode()
    return hashlib.sha256(payload).hexdigest()


def round_robin_indices(item_count: int, shard_count: int, shard_index: int) -> tuple[list[int], list[int]]:
    if item_count < 0:
        raise ValueError("item_count must not be negative")
    if shard_count < 1:
        raise ValueError("shard_count must be positive")
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must identify a shard")

    selected = list(range(shard_index, item_count, shard_count))
    selected_set = set(selected)
    deselected = [index for index in range(item_count) if index not in selected_set]
    return selected, deselected


def pytest_split_arguments(
    shard_count: int,
    shard_index: int,
    duration_manifest: Path,
    *,
    algorithm: str = "least_duration",
) -> list[str]:
    if shard_count < 1:
        raise ValueError("shard_count must be positive")
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must identify a shard")
    if shard_count == 1:
        return []
    if algorithm != "least_duration":
        raise ValueError(f"Unsupported splitting algorithm: {algorithm}")
    arguments = [
        f"--splitting-algorithm={algorithm}",
        f"--splits={shard_count}",
        f"--group={shard_index + 1}",
    ]
    arguments.insert(1, f"--durations-path={duration_manifest}")
    return arguments
