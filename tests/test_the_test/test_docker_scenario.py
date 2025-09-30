from threading import RLock
import pytest

from utils._context._scenarios.endtoend import DockerScenario
from utils._context.containers import TestedContainer as _TestedContainer
from utils import scenarios


class FakeContainer(_TestedContainer):
    def __init__(self, name, events=None) -> None:
        super().__init__(name=name, image_name=name)
        self._test_events = events if events is not None else []

    def configure(self, *, host_log_folder, replay):  # noqa: ARG002
        self._starting_lock = RLock()

    def start(self, network):  # noqa: ARG002
        self._test_events.append(f"start {self.name}")
        self.healthy = True

    def remove(self):
        pass


@scenarios.test_the_test
def test_main():
    events: list[str] = []

    class FakeScenario(DockerScenario):
        def __init__(self) -> None:
            super().__init__(name="fake_scenario", github_workflow=None, doc="")

            container_a = FakeContainer("A", events)
            container_b = FakeContainer("B", events)
            container_c = FakeContainer("C", events)
            container_d = FakeContainer("D", events)

            container_a.depends_on.append(container_b)
            container_a.depends_on.append(container_c)
            container_b.depends_on.append(container_d)
            container_c.depends_on.append(container_d)
            container_b.depends_on.append(container_c)

            self._required_containers = [container_a, container_b, container_c, container_d]

    scenario = FakeScenario()
    scenario.configure(None)
    scenario.pytest_sessionstart(None)

    assert events == ["start D", "start C", "start B", "start A"]


@scenarios.test_the_test
def test_recursive():
    class FakeScenario(DockerScenario):
        def __init__(self) -> None:
            super().__init__(name="fake_scenario", github_workflow=None, doc="")

            container_a = FakeContainer("A")
            container_b = FakeContainer("B")
            container_c = FakeContainer("C")

            container_a.depends_on.append(container_b)
            container_b.depends_on.append(container_c)
            container_c.depends_on.append(container_a)

            self._required_containers = [container_a, container_b, container_c]

    scenario = FakeScenario()
    with pytest.raises(RuntimeError):
        scenario.pytest_sessionstart(None)


@scenarios.test_the_test
def test_recursive_2():
    """More complex"""

    class FakeScenario(DockerScenario):
        def __init__(self) -> None:
            super().__init__(name="fake_scenario", github_workflow=None, doc="")

            container_a = FakeContainer("A")
            container_b = FakeContainer("B")
            container_c = FakeContainer("D")
            container_d = FakeContainer("E")
            container_e = FakeContainer("F")
            container_f = FakeContainer("G")
            container_g = FakeContainer("G")

            container_a.depends_on.append(container_b)
            container_b.depends_on.append(container_c)
            container_c.depends_on.append(container_d)
            container_d.depends_on.append(container_e)
            container_e.depends_on.append(container_f)
            container_f.depends_on.append(container_g)
            container_g.depends_on.append(container_c)

            self._required_containers = [container_a]

    scenario = FakeScenario()
    with pytest.raises(RuntimeError):
        scenario.pytest_sessionstart(None)
