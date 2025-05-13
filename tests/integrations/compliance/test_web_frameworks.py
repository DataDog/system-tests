from utils import interfaces, weblog, context
from .loader import load_schema
from .validator import assert_required_keys
from .report import generate_compliance_report


class Test_WebFrameworks:
    def setup_simple(self):
        self.r = weblog.get("/")

    def test_simple(self):
        schema = load_schema("web_frameworks")
        root_span = interfaces.library.get_root_span(self.r)

        missing, deprecated = assert_required_keys(root_span, schema)

        generate_compliance_report(
            category="web_framework", name=context.weblog_variant, missing=missing, deprecated=deprecated
        )

        if missing:
            raise AssertionError(f"Missing required attributes: {missing}")
