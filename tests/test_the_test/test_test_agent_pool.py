from utils.docker_fixtures._test_agent_pool import AgentLease, WorkerAgentPool, agent_env_key


class _FakeApi:
    def __init__(self) -> None:
        self.clear_calls = 0
        self.reset_rc_calls = 0
        self.rebind_calls: list[object] = []

    def clear(self) -> None:
        self.clear_calls += 1

    def reset_remote_config(self) -> None:
        self.reset_rc_calls += 1

    def rebind_request(self, request: object) -> None:
        self.rebind_calls.append(request)


class _FakeCreator:
    """Records every creation and hands back a lease whose stop() is tracked."""

    def __init__(self) -> None:
        self.created_envs: list[dict] = []
        self.stopped = 0

    def __call__(self, request: object, agent_env: dict[str, str]) -> AgentLease:  # noqa: ARG002
        self.created_envs.append(dict(agent_env))
        api = _FakeApi()

        def _stop() -> None:
            self.stopped += 1

        return AgentLease(api=api, stop=_stop)


def test_env_key_is_order_independent():
    assert agent_env_key({"A": "1", "B": "2"}) == agent_env_key({"B": "2", "A": "1"})


def test_same_env_reuses_and_clears():
    creator = _FakeCreator()
    pool = WorkerAgentPool(creator)

    api1 = pool.acquire(request="req1", agent_env={})
    api2 = pool.acquire(request="req2", agent_env={})

    assert api1 is api2  # reused, not recreated
    assert len(creator.created_envs) == 1  # created exactly once
    assert api1.clear_calls == 2  # cleared on both acquires (first + reuse)
    assert api1.reset_rc_calls == 2  # remote-config reset on both acquires too
    assert api1.rebind_calls == ["req2"]  # rebound only on reuse, not on first acquire


def test_distinct_env_creates_separate_agents():
    creator = _FakeCreator()
    pool = WorkerAgentPool(creator)

    a = pool.acquire(request="r", agent_env={})
    b = pool.acquire(request="r", agent_env={"DD_ENV": "prod"})

    assert a is not b
    assert len(creator.created_envs) == 2


def test_shutdown_stops_every_lease():
    creator = _FakeCreator()
    pool = WorkerAgentPool(creator)
    pool.acquire(request="r", agent_env={})
    pool.acquire(request="r", agent_env={"DD_ENV": "prod"})

    pool.shutdown()

    assert creator.stopped == 2
    # After shutdown the cache is empty: acquiring again creates anew.
    pool.acquire(request="r", agent_env={})
    assert len(creator.created_envs) == 3
