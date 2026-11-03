"""Ensure the RC assertion rejects missing, intermittent, and false advertisements."""

import base64
from typing import Any

from tests.parametric.test_ffe.utils import assert_dependent_flag_capability
from utils import features, pytest, scenarios


def _request(mask: int, *, byte_array: bool) -> dict[str, Any]:
    raw = mask.to_bytes(7, byteorder="big")
    return {
        "body": {
            "client": {"id": "ffe-client", "capabilities": list(raw) if byte_array else base64.b64encode(raw).decode()}
        }
    }


@scenarios.test_the_test
@features.not_reported
class Test_FFE_RC_Capability_Assertion:
    @pytest.mark.parametrize("byte_array", [False, True])
    def test_supported_and_legacy(self, *, byte_array: bool) -> None:
        assert_dependent_flag_capability([_request((1 << 46) | (1 << 50), byte_array=byte_array)], supported=True)
        assert_dependent_flag_capability([_request(1 << 46, byte_array=byte_array)], supported=False)

    @pytest.mark.parametrize("byte_array", [False, True])
    def test_missing_bit_fails_even_if_later_poll_recovers(self, *, byte_array: bool) -> None:
        requests = [_request(1 << 46, byte_array=byte_array), _request((1 << 46) | (1 << 50), byte_array=byte_array)]
        with pytest.raises(AssertionError, match="bit 50=True"):
            assert_dependent_flag_capability(requests, supported=True)

    def test_false_advertisement_fails(self) -> None:
        with pytest.raises(AssertionError, match="bit 50=False"):
            assert_dependent_flag_capability([_request(1 << 50, byte_array=False)], supported=False)

    def test_no_traffic_is_not_a_pass(self) -> None:
        with pytest.raises(AssertionError, match="No FFE_FLAGS RC requests"):
            assert_dependent_flag_capability([], supported=False)
