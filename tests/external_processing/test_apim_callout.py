import re
import time
from collections import defaultdict
from pathlib import Path

from utils import context, features, interfaces, irrelevant, weblog
from utils._weblog import HttpResponse
from utils.dd_types import DataDogLibrarySpan


CALLOUT_LOG_PATTERN = re.compile(
    r'apim-gateway callout phase=(?P<phase><[^>]+>) request-id="(?P<request_id>[^"]+)" path="(?P<path>[^"]+)" outcome=ok'
)
DEFERRED_PHASES = ("<RequestHeaders>", "<RequestBody>", "<ResponseHeaders>", "<ResponseBody>")
INLINE_PHASES = ("<RequestHeaders>", "<ResponseHeaders>")
APIM_SPAN = ("web", "server", "apim-callout")
DEFAULT_PROBE_PATH = "/?probe=default-four-call"
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


def _assert_probe_phases(probe_path: str, expected_phases: tuple[str, ...]) -> None:
    matching_groups = {
        request_id: phases
        for (request_id, path), phases in _callout_phases_by_request_id_and_path().items()
        if path == probe_path
    }
    assert len(matching_groups) == 1
    assert next(iter(matching_groups.values())) == list(expected_phases)


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
    def setup_default_body_mode_uses_four_callouts(self):
        self.r = weblog.post(DEFAULT_PROBE_PATH, json={"body": "default"})

    def test_default_body_mode_uses_four_callouts(self):
        assert self.r.status_code == 200
        _assert_probe_phases(DEFAULT_PROBE_PATH, DEFERRED_PHASES)

    def setup_inline_body_mode_uses_two_callouts(self):
        self.r = weblog.post(INLINE_PROBE_PATH, json={"body": "inline"}, headers={"X-Datadog-Apim-Body-Mode": "inline"})

    def test_inline_body_mode_uses_two_callouts(self):
        assert self.r.status_code == 200
        _assert_probe_phases(INLINE_PROBE_PATH, INLINE_PHASES)

    def setup_inline_body_mode_preserves_trace_structure(self):
        self.default_response = weblog.post(TRACE_DEFAULT_PROBE_PATH, json={"body": "default trace"})
        self.inline_response = weblog.post(
            TRACE_INLINE_PROBE_PATH,
            json={"body": "inline trace"},
            headers={"X-Datadog-Apim-Body-Mode": "inline"},
        )

    def test_inline_body_mode_preserves_trace_structure(self):
        assert self.default_response.status_code == 200
        assert self.inline_response.status_code == 200
        _assert_probe_phases(TRACE_DEFAULT_PROBE_PATH, DEFERRED_PHASES)
        _assert_probe_phases(TRACE_INLINE_PROBE_PATH, INLINE_PHASES)
        assert _trace_structure(self.default_response) == _trace_structure(self.inline_response)

    def setup_inline_body_mode_closes_request_state(self):
        self.r = weblog.post(
            STATE_CLOSURE_PROBE_PATH,
            json={"body": "inline state"},
            headers={"X-Datadog-Apim-Body-Mode": "inline"},
        )
        time.sleep(31)

    def test_inline_body_mode_closes_request_state(self):
        assert self.r.status_code == 200
        _assert_probe_phases(STATE_CLOSURE_PROBE_PATH, INLINE_PHASES)
        assert "closing orphaned span" not in _container_stderr("apim-callout")
