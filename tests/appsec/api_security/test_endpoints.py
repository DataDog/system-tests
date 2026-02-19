from utils import interfaces, rfc, scenarios, weblog, features
from utils._weblog import HttpResponse


def assert_llm_span(request: HttpResponse, model: str) -> None:
    """Common assertions for LLM endpoint spans."""
    span = interfaces.library.get_root_span(request)
    assert span["meta"]["appsec.events.llm.call.provider"] == "openai"
    assert span["meta"]["appsec.events.llm.call.model"] == model
    assert span["metrics"]["_sampling_priority_v1"] == 1


@rfc(
    "https://docs.google.com/document/d/1TIFxbtbkldjOA6S5JFlCTMfqniXfJXZmDKptI5w2pnk/edit?tab=t.0#heading=h.xtljwwxyhqk7"
)
@scenarios.appsec_api_security
@features.api_llm_endpoint
class Test_LLM_Endpoint:
    """Tests for the /llm endpoint capturing LLM interaction metadata."""

    MODEL = "gpt-4.1"

    def setup_openai_latest_responses_create(self):
        self.request = weblog.get(f"/llm?model={self.MODEL}&operation=openai-latest-responses.create")

    def test_openai_latest_responses_create(self):
        assert_llm_span(self.request, self.MODEL)

    def setup_openai_latest_chat_completions_create(self):
        self.request = weblog.get(f"/llm?model={self.MODEL}&operation=openai-latest-chat.completions.create")

    def test_openai_latest_chat_completions_create(self):
        assert_llm_span(self.request, self.MODEL)

    def setup_openai_latest_completions_create(self):
        self.request = weblog.get(f"/llm?model={self.MODEL}&operation=openai-latest-completions.create")

    def test_openai_latest_completions_create(self):
        assert_llm_span(self.request, self.MODEL)

    def setup_openai_legacy_chat_completions_create(self):
        self.request = weblog.get(f"/llm?model={self.MODEL}&operation=openai-legacy-chat.completions.create")

    def test_openai_legacy_chat_completions_create(self):
        assert_llm_span(self.request, self.MODEL)

    def setup_openai_legacy_completions_create(self):
        self.request = weblog.get(f"/llm?model={self.MODEL}&operation=openai-legacy-completions.create")

    def test_openai_legacy_completions_create(self):
        assert_llm_span(self.request, self.MODEL)

    def setup_openai_async_responses_create(self):
        self.request = weblog.get(f"/llm?model={self.MODEL}&operation=openai-async-responses.create")

    def test_openai_async_responses_create(self):
        assert_llm_span(self.request, self.MODEL)

    def setup_openai_async_chat_completions_create(self):
        self.request = weblog.get(f"/llm?model={self.MODEL}&operation=openai-async-chat.completions.create")

    def test_openai_async_chat_completions_create(self):
        assert_llm_span(self.request, self.MODEL)

    def setup_openai_async_completions_create(self):
        self.request = weblog.get(f"/llm?model={self.MODEL}&operation=openai-async-completions.create")

    def test_openai_async_completions_create(self):
        assert_llm_span(self.request, self.MODEL)

    def setup_root_no_llm(self):
        # Baseline request to root endpoint should not produce LLM tags
        self.root_request = weblog.get("/")

    def test_root_has_no_llm_tags(self):
        """Assert that LLM-specific meta tags are not present on the span."""
        span = interfaces.library.get_root_span(self.root_request)
        meta = span.get("meta", {})
        assert "appsec.events.llm.call.provider" not in meta
        assert "appsec.events.llm.call.model" not in meta
