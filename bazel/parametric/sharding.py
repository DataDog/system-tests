from __future__ import annotations


def pytest_split_arguments(shard_count: int, shard_index: int) -> list[str]:
    if shard_count < 1:
        raise ValueError("shard_count must be positive")
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must identify a shard")
    if shard_count == 1:
        return []
    return [
        "--splitting-algorithm=least_duration",
        f"--splits={shard_count}",
        f"--group={shard_index + 1}",
    ]
