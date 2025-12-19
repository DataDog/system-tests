import enum
from pathlib import Path


reason_regex = r" ?(?:\((.*)\))?"
skip_declaration_regex = rf"(bug|flaky|incomplete_test_app|irrelevant|missing_feature){reason_regex}"
version_regex = r"(?:\d+\.\d+\.\d+|\d+\.\d+|\d+)[.+-]?[.\w+-]*"
simple_regex = rf"(>|>=|v)?({version_regex}){reason_regex}"
full_regex = rf"(v)?([^()]*){reason_regex}"
default_manifests_path = Path("manifests/")


class TestDeclaration(enum.StrEnum):
    __test__ = False  # Tell pytest this is not a test class
    BUG = "bug"
    FLAKY = "flaky"
    INCOMPLETE_TEST_APP = "incomplete_test_app"
    IRRELEVANT = "irrelevant"
    MISSING_FEATURE = "missing_feature"
