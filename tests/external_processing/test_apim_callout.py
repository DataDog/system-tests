import re
from collections import defaultdict
from pathlib import Path
import time

from utils import context, features, interfaces, irrelevant, weblog
from utils._weblog import HttpResponse
from utils.dd_types import DataDogLibrarySpan


CALLOUT_LOG_PATTERN = re.compile(
    r'apim-gateway callout phase=(?P<phase><[^>]+>) request-id="(?P<request_id>[^"]+)" path="(?P<path>[^"]+)" outcome=ok'
)
# Deferred (default) body mode: the bodies are not inlined, so the <RequestHeaders> callout answers
# with `allowed-body-size` and the gateway makes a separate <RequestBody> call. These three phases
# are guaranteed, in this order.
DEFERRED_PHASES = ("<RequestHeaders>", "<RequestBody>", "<ResponseHeaders>")
# Inline body mode: both bodies ride along on the header calls, which is exactly what suppresses
# `allowed-body-size`, so no body phase is ever requested on either side.
INLINE_PHASES = ("<RequestHeaders>", "<ResponseHeaders>")
# A fourth <ResponseBody> phase is possible but NOT guaranteed, so it is tolerated and never
# required. The gateway only makes it when the <ResponseHeaders> callout answers with
# `allowed-body-size`, and the callout only asks for the response body when the upstream returned
# one it can parse. That is a property of the upstream, not of the gateway: the stock `http-app`
# (jasonrm/dummy-server) answers every request with `text/plain` containing the status code, so
# this phase never fires in CI. Do not turn it back into a required phase after validating against
# a substituted upstream -- a JSON-returning stand-in makes it fire and hides this distinction.
UPSTREAM_DEPENDENT_PHASE = "<ResponseBody>"
APIM_SPAN = ("web", "server", "apim-callout")
DEFAULT_PROBE_PATH = "/?probe=default-deferred-body"
INLINE_PROBE_PATH = "/?probe=inline-two-call"
TRACE_DEFAULT_PROBE_PATH = "/?probe=trace-default"
TRACE_INLINE_PROBE_PATH = "/?probe=trace-inline"
STATE_CLOSURE_PROBE_PATH = "/?probe=inline-state-closure"


def _container_stderr(container_name: str) -> str:
    log_path = Path(context.scenario.host_log_folder) / "docker" / container_name / "stderr.log"
    return log_path.read_text(encoding="utf-8")


def _callout_phases_by_request_id_and_path() -> dict[tuple[str, str], list[str]]:
    phases_by_request_id_and_path: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for line in _container_stderr("apim-gateway").splitlines():
        if match := CALLOUT_LOG_PATTERN.fullmatch(line):
            key = match.group("request_id"), match.group("path")
            phases_by_request_id_and_path[key].append(match.group("phase"))

    return dict(phases_by_request_id_and_path)


def _probe_phase_group(probe_path: str) -> tuple[str, list[str]]:
    """Return the (request-id, phases) of the single callout group that belongs to `probe_path`.

    Every request reaching the gateway -- including its own bodiless healthcheck -- appends to the
    same stderr log, so phases are correlated by (request-id, path) and never counted globally.
    Each probe path is requested exactly once, so exactly one group must match. Zero groups means
    the gateway log format drifted away from CALLOUT_LOG_PATTERN, which would otherwise make every
    phase assertion below pass vacuously.
    """
    matching_groups = {
        request_id: phases
        for (request_id, path), phases in _callout_phases_by_request_id_and_path().items()
        if path == probe_path
    }
    assert len(matching_groups) == 1, (
        f"expected exactly one callout request-id group for probe {probe_path}, "
        f"got {len(matching_groups)}: {sorted(matching_groups)}"
    )
    return next(iter(matching_groups.items()))


def _assert_deferred_probe_phases(probe_path: str) -> None:
    """Assert `probe_path` was served in deferred body mode: a separate <RequestBody> callout.

    A single trailing <ResponseBody> is accepted because it depends on the upstream returning a
    parseable response body (see UPSTREAM_DEPENDENT_PHASE); everything before it is required.
    """
    request_id, phases = _probe_phase_group(probe_path)
    required_phases = phases[:-1] if phases[-1:] == [UPSTREAM_DEPENDENT_PHASE] else phases
    assert required_phases == list(DEFERRED_PHASES), (
        f"deferred probe {probe_path} (request-id {request_id}) hit callout phases {phases}, "
        f"expected {list(DEFERRED_PHASES)} optionally followed by {UPSTREAM_DEPENDENT_PHASE}"
    )


def _assert_inline_probe_phases(probe_path: str) -> str:
    """Assert `probe_path` was served in inline body mode: header phases only, no body phase.

    Returns the request-id, so a caller can scope further assertions to this exchange.
    """
    request_id, phases = _probe_phase_group(probe_path)
    assert phases == list(INLINE_PHASES), (
        f"inline probe {probe_path} (request-id {request_id}) hit callout phases {phases}, "
        f"expected {list(INLINE_PHASES)}"
    )
    return request_id


def _span_structure(span: DataDogLibrarySpan) -> tuple[str, str, str]:
    return span["type"], span["meta"]["span.kind"], span["meta"]["component"]


def _assert_apim_span(span: DataDogLibrarySpan) -> None:
    assert _span_structure(span) == APIM_SPAN


def _trace_structure(request: HttpResponse) -> list[tuple[str, str, str]]:
    interfaces.library.assert_trace_exists(request=request)
    assert _span_structure(interfaces.library.get_root_span(request=request)) == APIM_SPAN
    interfaces.library.validate_all_spans(request=request, validator=_assert_apim_span)
    return sorted(_span_structure(span) for _, _, span in interfaces.library.get_spans(request=request))


@irrelevant(context.weblog_variant != "apim")
@features.go_proxies
class Test_ApimCallout:
    def setup_default_body_mode_defers_request_body_callout(self) -> None:
        self.r = weblog.post(DEFAULT_PROBE_PATH, json={"body": "default"})

    def test_default_body_mode_defers_request_body_callout(self) -> None:
        """Without the inline header, the request body is fetched by its own <RequestBody> callout."""
        assert self.r.status_code == 200, f"deferred probe returned {self.r.status_code}, expected 200"
        _assert_deferred_probe_phases(DEFAULT_PROBE_PATH)

    def setup_inline_body_mode_uses_two_callouts(self) -> None:
        self.r = weblog.post(INLINE_PROBE_PATH, json={"body": "inline"}, headers={"X-Datadog-Apim-Body-Mode": "inline"})

    def test_inline_body_mode_uses_two_callouts(self) -> None:
        """Inlining the body on the header calls removes the body phases, leaving exactly two calls."""
        assert self.r.status_code == 200, f"inline probe returned {self.r.status_code}, expected 200"
        _assert_inline_probe_phases(INLINE_PROBE_PATH)

    def setup_inline_body_mode_preserves_trace_structure(self) -> None:
        self.default_response = weblog.post(TRACE_DEFAULT_PROBE_PATH, json={"body": "default trace"})
        self.inline_response = weblog.post(
            TRACE_INLINE_PROBE_PATH,
            json={"body": "inline trace"},
            headers={"X-Datadog-Apim-Body-Mode": "inline"},
        )

    def test_inline_body_mode_preserves_trace_structure(self) -> None:
        assert self.default_response.status_code == 200, (
            f"deferred probe returned {self.default_response.status_code}, expected 200"
        )
        assert self.inline_response.status_code == 200, (
            f"inline probe returned {self.inline_response.status_code}, expected 200"
        )
        _assert_deferred_probe_phases(TRACE_DEFAULT_PROBE_PATH)
        _assert_inline_probe_phases(TRACE_INLINE_PROBE_PATH)
        default_spans = _trace_structure(self.default_response)
        inline_spans = _trace_structure(self.inline_response)
        assert default_spans == inline_spans, (
            f"inline body delivery changed the trace: deferred spans {default_spans}, inline spans {inline_spans}"
        )

    def setup_inline_body_mode_closes_request_state(self) -> None:
        self.r = weblog.post(
            STATE_CLOSURE_PROBE_PATH,
            json={"body": "inline state"},
            headers={"X-Datadog-Apim-Body-Mode": "inline"},
        )
        # Keep the callout alive beyond its configured 2s request-state TTL. If inline response
        # handling leaves the state cached, the live expiry sweep logs the orphan before teardown.
        time.sleep(3)

    def test_inline_body_mode_closes_request_state(self) -> None:
        assert self.r.status_code == 200, f"inline probe returned {self.r.status_code}, expected 200"
        request_id = _assert_inline_probe_phases(STATE_CLOSURE_PROBE_PATH)
        orphaned = [
            line
            for line in _container_stderr("apim-callout").splitlines()
            if "closing orphaned span" in line and request_id in line
        ]
        assert not orphaned, (
            f"apim-callout orphaned the cached state for inline request-id {request_id}, "
            f"so inline mode did not close it: {orphaned}"
        )
