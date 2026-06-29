from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from utils._logger import logger


def agent_env_key(agent_env: dict[str, str]) -> tuple:
    """Stable, hashable, order-independent key for an agent_env dict."""
    return tuple(sorted(agent_env.items()))


@dataclass
class AgentLease:
    """One running test-agent (+ its network) owned by the pool.

    `api` is a TestAgentAPI (duck-typed here so this module stays Docker-free).
    `stop` tears the lease down (container + network); it must be idempotent-safe
    to call exactly once at shutdown.
    """

    api: Any
    stop: Callable[[], None]


class WorkerAgentPool:
    """Per-worker cache of test-agents keyed by agent_env.

    First request for a given env creates a lease via `creator`; later requests
    for the same env reuse it after `api.clear()` (reset state) and
    `api.rebind_request()` (re-point per-test logging at the current test).
    """

    def __init__(self, creator: Callable[[Any, dict[str, str]], AgentLease]) -> None:
        self._creator = creator
        self._leases: dict[tuple, AgentLease] = {}

    # request/return are duck-typed (a real FixtureRequest + TestAgentAPI in prod, fakes in
    # tests); Any keeps this module Docker-free.
    def acquire(self, request: Any, agent_env: dict[str, str]) -> Any:  # noqa: ANN401
        key = agent_env_key(agent_env)
        lease = self._leases.get(key)
        if lease is None:
            lease = self._creator(request, agent_env)
            self._leases[key] = lease
        else:
            lease.api.rebind_request(request)
        lease.api.clear()  # always return a clean agent (covers first acquire too)
        return lease.api

    def shutdown(self) -> None:
        for lease in self._leases.values():
            try:
                lease.stop()
            except Exception as e:
                logger.info(f"Error stopping pooled agent lease, ignoring: {e}")
        self._leases.clear()
