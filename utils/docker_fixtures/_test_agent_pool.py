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
    """

    # creator(request, agent_env) -> context manager yielding a TestAgentAPI. Duck-typed
    # (a real FixtureRequest + TestAgentAPI in prod, fakes in tests); Any keeps this
    # module Docker-free.
    def __init__(self, creator: Callable[[Any, dict[str, str]], AbstractContextManager[Any]]) -> None:
        self._creator = creator
        self._stack = contextlib.ExitStack()
        self._apis: dict[tuple, Any] = {}

    def acquire(self, request: Any, agent_env: dict[str, str]) -> Any:  # noqa: ANN401
        key = agent_env_key(agent_env)
        api = self._apis.get(key)
        if api is None:
            # Keep the agent open for the whole session; the ExitStack tears it (and its
            # network) down when the pool's context exits.
            api = self._stack.enter_context(self._creator(request, agent_env))
            self._apis[key] = api
        else:
            api.rebind_request(request)
        # Always hand back a fully reset agent (covers the first acquire too): drop
        # recorded requests, then restore the served remote-config to a fresh-agent
        # state. The RC reset is separate from clear() so mid-test clear=True helpers
        # don't wipe a test's active config.
        api.clear()
        api.reset_remote_config()
        return api

    def __exit__(self, *exc_info: object) -> None:
        try:
            self._stack.close()
        except Exception as e:
            logger.info(f"Error tearing down pooled agents, ignoring: {e}")
        finally:
            self._apis.clear()
