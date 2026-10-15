from collections.abc import Callable
import contextlib
from contextlib import AbstractContextManager
from typing import Any

from utils._logger import logger


def agent_env_key(agent_env: dict[str, str]) -> tuple:
    """Stable, hashable, order-independent key for an agent_env dict."""
    return tuple(sorted(agent_env.items()))


class WorkerAgentPool(contextlib.AbstractContextManager):
    """Per-worker cache of test-agents keyed by agent_env.

    First request for a given env opens an agent via `creator` (a context manager
    yielding a TestAgentAPI) and keeps it open for the whole worker session; later
    requests for the same env reuse it after clear()/reset_remote_config() (reset state)
    and rebind_request() (re-point per-test logging at the current test).

    Use as a context manager so every pooled agent is torn down exactly once at exit --
    consumers never call a shutdown method directly:

        with WorkerAgentPool(creator) as pool:
            api = pool.acquire(request, agent_env)

    Resilience: an agent is cached only after its reset succeeds, and a reset failure on
    a reused agent evicts and recreates it. That stops one dead/blipped agent from
    cascading into setup failures for every later poolable test on the worker.
    """

    # creator(request, agent_env) -> context manager yielding a TestAgentAPI. Duck-typed
    # (a real FixtureRequest + TestAgentAPI in prod, fakes in tests); Any keeps this
    # module Docker-free. Each entry keeps its own ExitStack so it can be torn down
    # individually (eviction) or in bulk (pool exit).
    def __init__(self, creator: Callable[[Any, dict[str, str]], AbstractContextManager[Any]]) -> None:
        self._creator = creator
        self._entries: dict[tuple, tuple[Any, contextlib.ExitStack]] = {}

    def acquire(self, request: Any, agent_env: dict[str, str]) -> Any:  # noqa: ANN401
        key = agent_env_key(agent_env)
        entry = self._entries.get(key)
        if entry is not None:
            api = entry[0]
            api.rebind_request(request)
            try:
                self._reset(api)
            except Exception as e:
                # Any reset failure means a dirty/dead agent. Don't let it cascade: drop
                # it and recreate below.
                logger.info(f"Pooled agent reset failed, recreating it: {e}")
                self._close_entry(key)
            else:
                return api
        return self._open_entry(key, request, agent_env)

    def _open_entry(self, key: tuple, request: Any, agent_env: dict[str, str]) -> Any:  # noqa: ANN401
        # Reset before caching so a create whose reset fails doesn't leave a broken entry.
        stack = contextlib.ExitStack()
        try:
            api = stack.enter_context(self._creator(request, agent_env))
            self._reset(api)
        except BaseException:
            stack.close()
            raise
        self._entries[key] = (api, stack)
        return api

    @staticmethod
    def _reset(api: Any) -> None:  # noqa: ANN401
        # Drop recorded requests, then restore the served remote-config to a fresh-agent
        # state. The RC reset is separate from clear() so mid-test clear=True helpers
        # don't wipe a test's active config.
        api.clear()
        api.reset_remote_config()

    def _close_entry(self, key: tuple) -> None:
        entry = self._entries.pop(key, None)
        if entry is not None:
            try:
                entry[1].close()
            except Exception as e:
                logger.info(f"Error tearing down pooled agent, ignoring: {e}")

    def __exit__(self, *exc_info: object) -> None:
        for key in list(self._entries):
            self._close_entry(key)
