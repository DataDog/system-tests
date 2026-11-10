"""Single-carrier virtual threads on JDK 21.

The weblog returns only if the tracer lets the carrier make progress. A hang fails the request
on the weblog timeout.
"""

from utils import interfaces, scenarios, weblog

_FANOUT_SPANS = 200


@scenarios.java_virtual_threads
class Test_JavaVirtualThreadCarrier:
    def setup_request_completes(self) -> None:
        self.response = weblog.get("/")

    def test_request_completes(self) -> None:
        """The first application request finishes and is traced."""
        assert self.response.status_code == 200
        interfaces.library.assert_trace_exists(self.response)

    def setup_fanout_completes(self) -> None:
        self.fanout = weblog.get("/virtual-threads/fanout", params={"spans": _FANOUT_SPANS})

    def test_fanout_completes(self) -> None:
        """Child spans finished from virtual threads do not stall the only carrier."""
        assert self.fanout.status_code == 200
        assert self.fanout.text == f"created {_FANOUT_SPANS} spans\n"
        interfaces.library.assert_trace_exists(self.fanout)
