# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import base64
import gzip
import json
import logging
import traceback

import msgpack
from requests_toolbelt.multipart.decoder import MultipartDecoder
from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
    ExportMetricsServiceResponse,
)
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
    ExportLogsServiceResponse,
)
from _decoders.protobuf_schemas import MetricPayload, TracePayload


logger = logging.getLogger(__name__)


def get_header_value(name, headers):
    return next((h[1] for h in headers if h[0].lower() == name.lower()), None)


def _parse_as_unsigned_int(value, size_in_bits):
    """This is necessary because some fields in spans are decribed as a 64 bits unsigned integers, but
    java, and other languages only supports signed integer. As such, they might send trace ids as negative
    number if >2**63 -1. The agent parses it signed and interpret the bytes as unsigned. See
    https://github.com/DataDog/datadog-agent/blob/778855c6c31b13f9235a42b758a1f7c8ab7039e5/pkg/trace/pb/decoder_bytes.go#L181-L196
    """
    if not isinstance(value, int):
        return value

    # Asserts that the unsigned is either a no bigger than the size in bits
    assert -(2**size_in_bits - 1) <= value <= 2**size_in_bits - 1

    # Take two's complement of the number if negative
    return value if value >= 0 else (-value ^ (2**size_in_bits - 1)) + 1


def _decode_unsigned_int_traces(content):
    for span in (span for trace in content for span in trace):
        for sub_key in ("trace_id", "parent_id", "span_id"):
            if sub_key in span:
                span[sub_key] = _parse_as_unsigned_int(span[sub_key], 64)


def _decode_v_0_5_traces(content):
    # https://github.com/DataDog/architecture/blob/master/rfcs/apm/agent/v0.5-endpoint/rfc.md
    strings, payload = content

    result = []
    for spans in payload:
        decoded_spans = []
        result.append(decoded_spans)
        for span in spans:
            decoded_span = {
                "service": strings[int(span[0])],
                "name": strings[int(span[1])],
                "resource": strings[int(span[2])],
                "trace_id": span[3],
                "span_id": span[4],
                "parent_id": span[5] if span[5] != 0 else None,
                "start": span[6],
                "duration": span[7] if span[7] != 0 else None,
                "error": span[8],
                "meta": {strings[int(key)]: strings[int(value)] for key, value in span[9].items()},
                "metrics": {strings[int(key)]: value for key, value in span[10].items()},
                "type": strings[int(span[11])],
            }

            decoded_spans.append(decoded_span)

    return result


def deserialize_dd_appsec_s_meta(payload):
    """meta value for _dd.appsec.s.<address> are b64 - gzip - json encoded strings"""

    try:
        return json.loads(gzip.decompress(base64.b64decode(payload)).decode())
    except Exception:
        # b64/gzip is optional
        return json.loads(payload)


def deserialize_http_message(path, message, content: bytes, interface, key):
    def json_load():
        if not content:
            return None

        return json.loads(content)

    content_type = get_header_value("content-type", message["headers"])
    content_type = None if content_type is None else content_type.lower()

    if content_type and any((mime_type in content_type for mime_type in ("application/json", "text/json"))):
        return json_load()

    if path == "/v0.7/config":  # Kyle, please add content-type header :)
        if key == "response" and message["status_code"] == 404:
            return content.decode(encoding="utf-8")
        else:
            return json_load()

    if interface == "library" and path == "/info":
        if key == "response":
            return json_load()
        else:
            if not content:
                return None
            else:
                return content

    if content_type in ("application/msgpack", "application/msgpack, application/msgpack"):
        result = msgpack.unpackb(content, unicode_errors="replace", strict_map_key=False)

        if interface == "library":
            if path == "/v0.4/traces":
                _decode_unsigned_int_traces(result)
                _deserialized_nested_json_from_trace_payloads(result, interface)

            elif path == "/v0.5/traces":
                result = _decode_v_0_5_traces(result)
                _decode_unsigned_int_traces(result)
                _deserialized_nested_json_from_trace_payloads(result, interface)

        _convert_bytes_values(result)

        return result

    if content_type == "application/x-protobuf":
        # Raw data can be either a str like "b'\n\x\...'" or bytes
        content = eval(content) if isinstance(content, str) else content
        assert isinstance(content, bytes)
        dd_protocol = get_header_value("dd-protocol", message["headers"])
        if dd_protocol == "otlp" and "traces" in path:
            return MessageToDict(ExportTraceServiceRequest.FromString(content))
        if dd_protocol == "otlp" and "metrics" in path:
            return MessageToDict(ExportMetricsServiceRequest.FromString(content))
        if dd_protocol == "otlp" and "logs" in path:
            return MessageToDict(ExportLogsServiceRequest.FromString(content))
        if path == "/v1/traces":
            return MessageToDict(ExportTraceServiceResponse.FromString(content))
        if path == "/v1/metrics":
            return MessageToDict(ExportMetricsServiceResponse.FromString(content))
        if path == "/v1/logs":
            return MessageToDict(ExportLogsServiceResponse.FromString(content))
        if path == "/api/v0.2/traces":
            result = MessageToDict(TracePayload.FromString(content))
            _deserialized_nested_json_from_trace_payloads(result, interface)
            return result
        if path == "/api/v2/series":
            return MessageToDict(MetricPayload.FromString(content))

    if content_type == "application/x-www-form-urlencoded" and content == b"[]" and path == "/v0.4/traces":
        return []

    if content_type and content_type.startswith("multipart/form-data;"):
        decoded = []
        for part in MultipartDecoder(content, content_type).parts:
            headers = {k.decode("utf-8"): v.decode("utf-8") for k, v in part.headers.items()}
            item = {"headers": headers}
            try:
                item["content"] = part.text
            except UnicodeDecodeError:
                item["content"] = part.content

            decoded.append(item)

        if path == "/debugger/v1/diagnostics":
            for item in decoded:
                if "content" in item:
                    try:
                        item["content"] = json.loads(item["content"])
                    except:
                        pass

        return decoded

    if content_type == "text/plain":
        return content.decode("ascii")

    if not content or len(content) == 0:
        return None

    return content


def _deserialized_nested_json_from_trace_payloads(content, interface):
    """trace payload from agent and library contains strings that are json"""

    if interface == "agent":
        for tracer_payload in content.get("tracerPayloads", []):
            for chunk in tracer_payload.get("chunks", []):
                for span in chunk.get("spans", []):
                    _deserialize_meta(span)

    elif interface == "library":
        for traces in content:
            for span in traces:
                _deserialize_meta(span)


def _deserialize_meta(span):

    meta = span.get("meta", {})

    keys = ("_dd.appsec.json", "_dd.iast.json")

    for key in list(meta):
        if key.startswith("_dd.appsec.s."):
            meta[key] = deserialize_dd_appsec_s_meta(meta[key])
        elif key in keys:
            meta[key] = json.loads(meta[key])


def _convert_bytes_values(item, path=""):
    if isinstance(item, dict):
        for key in item:
            if isinstance(item[key], bytes):
                if path == "[][].meta_struct":
                    # meta_struct value is msgpack in msgpack
                    try:
                        item[key] = msgpack.unpackb(item[key], unicode_errors="replace", strict_map_key=False)
                    except BaseException as e:
                        raise ValueError(f"Error decoding {path}") from e
                else:
                    # otherwise, best guess is simple string
                    try:
                        item[key] = item[key].decode("ascii")
                    except UnicodeDecodeError as e:
                        raise ValueError(f"Error decoding {path}") from e
            elif isinstance(item[key], dict):
                _convert_bytes_values(item[key], f"{path}.{key}")
    elif isinstance(item, (list, tuple)):
        for value in item:
            _convert_bytes_values(value, f"{path}[]")


def deserialize(data, key, content, interface):

    try:
        data[key]["content"] = deserialize_http_message(data["path"], data[key], content, interface, key)
    except:
        logger.exception(f"Error while deserializing {data['log_filename']}", exc_info=True)
        data[key]["raw_content"] = str(content)
        data[key]["traceback"] = str(traceback.format_exc())


# if __name__ == "__main__":
#     content = json.load(open("logs/interfaces/library/005__v0.5_traces.json"))["request"]["content"]
#     print(json.dumps(_decode_v_0_5_traces(content), indent=2))
