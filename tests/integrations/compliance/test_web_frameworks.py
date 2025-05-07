from utils import (
    interfaces,
    weblog,
)
from .loader import (
    load_schema,
)
from .validator import (
    assert_required_keys,
)


class Test_WebFrameworks:
    def setup_simple(self):
        self.r = weblog.get("/")

    def test_simple(self):
        root_span = interfaces.library.get_root_span(self.r)
        schema = load_schema("web_frameworks")
        required = schema["required_root_span_attributes"]
        assert_required_keys(root_span, required)
