# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import traceback
import ast
import msgpack
import json
from requests_toolbelt.multipart.decoder import MultipartDecoder
from utils.interfaces._decoders.protobuf_schemas import TracePayload
from google.protobuf.json_format import MessageToDict

from utils.tools import logger


def get_header_value(name, headers):
    return next((h[1] for h in headers if h[0].lower() == name.lower()), None)


def parse_as_unsigned_int(value, size_in_bits):
    """This is necessary because some fields in spans are decribed as a 64 bits unsigned integers, but
    java, and other languages only supports signed integer. As such, they might send trace ids as negative
    number if >2**63 -1. The agent parses it signed and interpret the bytes as unsigned. See
    https://github.com/DataDog/datadog-agent/blob/778855c6c31b13f9235a42b758a1f7c8ab7039e5/pkg/trace/pb/decoder_bytes.go#L181-L196"""
    if not isinstance(value, int):
        return value

    # Asserts that the unsigned is either a no bigger than the size in bits
    assert -(2 ** size_in_bits - 1) <= value <= 2 ** size_in_bits - 1

    # Take two's complement of the number if negative
    return value if value >= 0 else (-value ^ (2 ** size_in_bits - 1)) + 1


def deserialize_http_message(path, message, data, interface, key):
    if not isinstance(data, (str, bytes)):
        return data

    content_type = get_header_value("content-type", message["headers"])
    content_type = None if content_type is None else content_type.lower()

    logger.debug(f"Deserialize {content_type} for {path} {key}")

    if content_type in ("application/json", "text/json"):
        return json.loads(data)
    elif interface == "library" and key == "response" and path == "/info":
        return json.loads(data)
    elif content_type == "application/msgpack":
        result = msgpack.unpackb(data)

        if interface == "library" and path == "/v0.4/traces":
            for span in (span for trace in result for span in trace):
                for key in ("trace_id", "parent_id", "span_id"):
                    if key in span.keys():
                        span[key] = parse_as_unsigned_int(span[key], 64)
        elif interface == "library" and path == "/v0.6/stats":
            # TODO: decode OkSummary, Error
            return result

        _convert_bytes_values(result)

        return result

    elif content_type == "application/x-protobuf" and path == "/api/v0.2/traces":
        return MessageToDict(TracePayload.FromString(data))

    elif content_type == "application/x-www-form-urlencoded" and data == b"[]" and path == "/v0.4/traces":
        return []

    elif content_type and content_type.startswith("multipart/form-data;"):
        decoded = []
        for part in MultipartDecoder(data, content_type).parts:
            headers = {k.decode("utf-8"): v.decode("utf-8") for k, v in part.headers.items()}
            item = {"headers": headers}
            try:
                item["content"] = part.text
            except UnicodeDecodeError:
                item["content"] = part.content

            decoded.append(item)

        return decoded

    return data


def _convert_bytes_values(item):
    if isinstance(item, dict):
        for key in item:
            if isinstance(item[key], bytes):
                item[key] = item[key].decode("ascii")
            elif isinstance(item[key], dict):
                _convert_bytes_values(item[key])
    elif isinstance(item, (list, tuple)):
        for value in item:
            _convert_bytes_values(value)


def deserialize(data, interface):
    for key in ("request", "response"):
        try:
            content = ast.literal_eval(data[key]["content"])
            decoded = deserialize_http_message(data["path"], data[key], content, interface, key)
            data[key]["content"] = decoded
        except Exception as e:
            msg = traceback.format_exception_only(type(e), e)[0]
            logger.critical(msg)
