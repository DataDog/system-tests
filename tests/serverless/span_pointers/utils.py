from collections.abc import Callable
from hashlib import sha256
from typing import NewType

from utils import logger


PointerHash = NewType("PointerHash", str)

POINTER_DIRECTION_DOWNSTREAM = "d"
POINTER_DIRECTION_UPSTREAM = "d"


# copyied from https://github.com/DataDog/dd-span-pointer-rules/blob/main/test_py/test_rules.py
def standard_hashing_function(elements: list[bytes]) -> PointerHash:
    assert isinstance(elements, list)
    assert elements
    assert all(isinstance(element, bytes) for element in elements)

    separator = b"|"
    bits_per_hex_digit = 4
    desired_bits = 128
    hex_digits = desired_bits // bits_per_hex_digit

    hex_digest = sha256(separator.join(elements)).hexdigest()
    assert len(hex_digest) >= hex_digits

    return PointerHash(hex_digest[:hex_digits])


def make_single_span_link_validator(
    resource: str, pointer_kind: str, pointer_direction: str, pointer_hash: PointerHash
) -> Callable[[dict], bool | None]:
    """Make a validator function for use with interfaces.library.validate_spans.
    The validator checks that there is one and only one span pointer for the
    pointer_kind and pointer_direction and that its hash matches the
    pointer_hash.
    """

    def validator(span: dict) -> bool | None:
        logger.debug("checking span: %s", span)

        if "span_links" not in span:
            return None

        if "resource" not in span:
            return None

        if span["resource"] != resource:
            return None

        found_matching = False

        for span_link in span["span_links"]:
            attributes = span_link.get("attributes", {})
            if not attributes:
                continue

            if attributes.get("ptr.kind") != pointer_kind:
                continue

            if attributes.get("ptr.dir") != pointer_direction:
                continue

            assert not found_matching

            assert attributes.get("ptr.hash") == pointer_hash
            found_matching = True
            # we loop oonwards in caes there's unexpectedly more than one

        return found_matching

    return validator
