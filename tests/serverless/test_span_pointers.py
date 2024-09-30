import json
from hashlib import sha256
from typing import NewType

from utils import weblog, interfaces, rfc, features
from utils.tools import logger

PointerHash = NewType("PointerHash", str)


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


def _validate_hash_pointer(r):
    assert r.status_code == 200

    response_content = json.loads(r.text)
    bucket = r.request.params["bucket"].encode("ascii")
    key = r.request.params["key"].encode("utf-8")
    etag = response_content["object"]["e_tag"].encode("ascii")

    logger.info(f"bucket: {bucket}, key: {key}, etag: {etag}")

    def validator(span):
        if "span_links" not in span:
            return

        logger.info("Found span_links")

        for span_link in span["span_links"]:
            if "attributes" in span_link and "ptr.hash" in span_link["attributes"]:
                pointer_hash = span_link["attributes"]["ptr.hash"]
                assert pointer_hash == standard_hashing_function([bucket, key, etag])

                return True

    interfaces.library.validate_spans(r, validator=validator, full_trace=True)


@rfc("https://github.com/DataDog/dd-span-pointer-rules")
@features.serverless_span_pointers
class Test_SpanPointers:
    def setup_main(self):
        self.r = weblog.get("/mock_s3/put_object", params={"bucket": "mybucket", "key": "my-key"})

    def test_main(self):
        _validate_hash_pointer(self.r)

    def setup_non_ascii(self):
        self.r_non_ascii = weblog.get("/mock_s3/put_object", params={"bucket": "mybucket", "key": "some-key.你好"})

    def test_non_ascii(self):
        _validate_hash_pointer(self.r_non_ascii)
