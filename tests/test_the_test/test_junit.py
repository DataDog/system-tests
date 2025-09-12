from collections.abc import Iterable
import difflib
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom

import pytest
from utils import scenarios, features, irrelevant, bug, flaky

from .utils import run_system_tests


# keep this class in first, otherwise, you will need to update lines in observed every time you modify this file
@scenarios.mock_the_test
@features.adaptive_sampling
class Test_Cases:
    def test_pass(self):
        assert True

    def test_fail(self):
        pytest.fail("dummy")

    @irrelevant(condition=True)
    def test_skipped(self):
        pytest.fail("dummy")

    @bug(condition=True, reason="APMRP-360")
    def test_xfail(self):
        pytest.fail("dummy")

    @bug(condition=True, reason="APMRP-360")
    def test_xpass(self):
        assert True

    @flaky(condition=True, reason="APMRP-360")
    def test_flaky(self): ...


@scenarios.test_the_test
def test_main():
    run_system_tests(test_path="tests/test_the_test/test_junit.py", expected_return_code=1)

    observed = _normalize_etree("logs_mock_the_test/reportJunit.xml")
    expected = _normalize_etree("tests/test_the_test/reportJunit_expected.xml")

    if observed == expected:
        return

    diff = "\n".join(difflib.unified_diff(observed, expected, lineterm=""))
    pytest.fail(f"XML documents differ:\n{diff}")


def _normalize_etree(filename: str, ignore_attrs: Iterable[str] | None = None) -> list[str]:
    """Parse XML, drop selected attributes, and return normalized root element."""

    root = ET.parse(filename).getroot()  # noqa: S314

    ignore_attrs = {"timestamp", "time", "hostname"}

    for el in root.iter():
        # Sort attributes for stable output
        el.attrib = dict(sorted(el.attrib.items()))

        # clean values from moving parts
        for attr in ignore_attrs:
            el.attrib.pop(attr, None)

    # Pretty-print XML for diffing (ElementTree alone doesn't indent)
    rough = ET.tostring(root, encoding="utf-8")

    # clean moving parts

    cleaned_rough = re.sub(rb"0x[0-9abcdef]{8,}", b"0xhash", rough)
    lines = minidom.parseString(cleaned_rough).toprettyxml(indent="  ").splitlines()  # noqa: S318

    return [line for line in lines if len(line.strip()) != 0]
