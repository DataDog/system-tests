# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import base64
import gzip
import io
import json
import logging
from hashlib import md5
from http import HTTPStatus
import traceback
from typing import Any

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
from _decoders.protobuf_schemas import MetricPayload, TracePayload, SketchPayload


logger = logging.getLogger(__name__)


def get_header_value(name: str, headers: list[tuple[str, str]]):
    return next((h[1] for h in headers if h[0].lower() == name.lower()), None)


def _parse_as_unsigned_int(value: int, size_in_bits: int) -> int:
    """Some fields in spans are decribed as a 64 bits unsigned integers, but
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


def _decode_unsigned_int_traces(content: list):
    for span in (span for trace in content for span in trace):
        for sub_key in ("trace_id", "parent_id", "span_id"):
            if sub_key in span:
                span[sub_key] = _parse_as_unsigned_int(span[sub_key], 64)


def _decode_v_0_5_traces(content: tuple):
    # https://github.com/DataDog/architecture/blob/master/rfcs/apm/agent/v0.5-endpoint/rfc.md
    strings, payload = content

    result = []
    for spans in payload:
        decoded_spans: list = []
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


def deserialize_dd_appsec_s_meta(payload: str):
    """Meta value for _dd.appsec.s.<address> are b64 - gzip - json encoded strings"""

    try:
        return json.loads(gzip.decompress(base64.b64decode(payload)).decode())
    except Exception:
        # b64/gzip is optional
        return json.loads(payload)


def deserialize_http_message(
    path: str, message: dict, content: bytes | None, interface: str, key: str, export_content_files_to: str
):
    def json_load():
        if not content:
            return None

        return json.loads(content)

    raw_content_type = get_header_value("content-type", message["headers"])
    content_type = None if raw_content_type is None else raw_content_type.lower()

    # Determine if the content is from a Datadog tracer
    source_is_datadog_tracer = interface in (
        "library",
        "python_buddy",
        "nodejs_buddy",
        "java_buddy",
        "ruby_buddy",
        "golang_buddy",
    )

    if not content or len(content) == 0:
        return None

    if content_type and any(mime_type in content_type for mime_type in ("application/json", "text/json")):
        return json_load()

    if path == "/v0.7/config":  # Kyle, please add content-type header :)
        if key == "response" and message["status_code"] == HTTPStatus.NOT_FOUND:
            return content.decode(encoding="utf-8")

        return json_load()

    if path == "/dogstatsd/v2/proxy" and source_is_datadog_tracer:
        # TODO : how to deserialize this ?
        return content.decode(encoding="utf-8")

    if source_is_datadog_tracer and path == "/info":
        if key == "response":
            return json_load()

        # replace zero length strings/bytes by None
        return content if content else None

    if content_type in ("application/msgpack", "application/msgpack, application/msgpack") or (path == "/v0.6/stats"):
        result = msgpack.unpackb(content, unicode_errors="replace", strict_map_key=False)

        if source_is_datadog_tracer:
            if path == "/v0.4/traces":
                _decode_unsigned_int_traces(result)
                _deserialized_nested_json_from_trace_payloads(result, interface)

            elif path == "/v0.5/traces":
                result = _decode_v_0_5_traces(result)
                _decode_unsigned_int_traces(result)
                _deserialized_nested_json_from_trace_payloads(result, interface)

            elif path == "/v0.6/stats":
                # TODO : more strange stuff inside to deserialize
                # ddsketch protobuf in content.stats[].stats.OkSummary  and ErrorSummary
                # https://github.com/DataDog/sketches-go/blob/master/ddsketch/pb/ddsketch.proto#L15
                pass

        _convert_bytes_values(result)

        return result

    if content_type == "application/x-protobuf":
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
            try:
                return MessageToDict(MetricPayload.FromString(content))
            except Exception as e:
                return {
                    "content-length": len(content),
                    "error": str(e),
                    "raw_content": repr(content),
                    "message": message,
                    "key": key,
                    "interface": interface,
                }
        if path == "/api/beta/sketches":
            return MessageToDict(SketchPayload.FromString(content))

    if content_type == "application/x-www-form-urlencoded" and content == b"[]" and path == "/v0.4/traces":
        return []

    if content_type and content_type.startswith("multipart/form-data;"):
        decoded = []
        for part in MultipartDecoder(content, raw_content_type).parts:
            headers = {k.decode("utf-8"): v.decode("utf-8") for k, v in part.headers.items()}
            item: dict[str, Any] = {"headers": headers}

            content_type_part = ""

            for name, value in headers.items():
                if name.lower() == "content-type":
                    content_type_part = value.lower()
                    break

            if content_type_part.startswith("application/json"):
                try:
                    item["content"] = json.loads(part.content)
                except json.decoder.JSONDecodeError:
                    item["system-tests-error"] = "Can't decode json file"
                    item["raw_content"] = repr(part.content)

            elif content_type_part == "application/gzip":
                try:
                    with gzip.GzipFile(fileobj=io.BytesIO(part.content)) as gz_file:
                        content = gz_file.read()
                except:
                    item["system-tests-error"] = "Can't decompress gzip data"
                    continue

                _deserialize_file_in_multipart_form_data(path, item, headers, export_content_files_to, content)

            elif content_type_part == "application/octet-stream":
                _deserialize_file_in_multipart_form_data(path, item, headers, export_content_files_to, part.content)

            else:
                try:
                    item["content"] = part.text
                except UnicodeDecodeError:
                    item["content"] = str(part.content)

            decoded.append(item)

        return decoded

    if content_type == "text/plain":
        return content.decode("ascii")

    return content


def _deserialize_file_in_multipart_form_data(
    path: str, item: dict, headers: dict, export_content_files_to: str, content: bytes
) -> None:
    content_disposition = headers.get("Content-Disposition", "")

    if not content_disposition.startswith("form-data"):
        item["system-tests-error"] = "Unknown content-disposition, please contact #apm-shared-testing"
        item["content"] = None

    else:
        meta_data = {}

        for part in content_disposition.split(";"):
            if "=" in part:
                key, value = part.split("=", 1)
                meta_data[key.strip()] = value.strip()

        if "filename" not in meta_data:
            item["system-tests-error"] = "Filename not found in content-disposition, please contact #apm-shared-testing"
        else:
            filename = meta_data["filename"].strip('"')
            item["system-tests-filename"] = filename

            if filename.lower().endswith(".gz"):
                filename = filename[:-3]

            content_is_deserialized = False
            if filename.lower().endswith(".json") or path in ("/symdb/v1/input", "/api/v2/debugger"):
                # when path == /symdb/v1/input or /api/v2/debugger, the content may be either raw json, or gizipped json
                # though, the file name may not always contains .json, so for this use case
                # we always try to deserialize the content as json
                try:
                    item["content"] = json.loads(content)
                    content_is_deserialized = True
                except (json.JSONDecodeError, UnicodeDecodeError):
                    item["system-tests-error"] = "Can't decode json file"

            if not content_is_deserialized:
                file_path = f"{export_content_files_to}/{md5(content).hexdigest()}_{filename}"

                item["system-tests-information"] = "File exported to a separated file"
                item["system-tests-file-path"] = file_path

                with open(file_path, "wb") as f:
                    f.write(content)


def _deserialized_nested_json_from_trace_payloads(content: Any, interface: str):  # noqa: ANN401
    """Trace payload from agent and library contains strings that are json"""

    if interface == "agent":
        for tracer_payload in content.get("tracerPayloads", []):
            for chunk in tracer_payload.get("chunks", []):
                for span in chunk.get("spans", []):
                    _deserialize_meta(span)

    elif interface == "library":
        for traces in content:
            for span in traces:
                _deserialize_meta(span)


def _deserialize_meta(span: dict):
    meta = span.get("meta", {})

    keys = ("_dd.appsec.json", "_dd.iast.json")

    for key in list(meta):
        if key.startswith("_dd.appsec.s."):
            meta[key] = deserialize_dd_appsec_s_meta(meta[key])
        elif key in keys:
            meta[key] = json.loads(meta[key])


def _convert_bytes_values(item: Any, path: str = ""):  # noqa: ANN401
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


def deserialize(data: dict[str, Any], key: str, content: bytes | None, interface: str, export_content_files_to: str):
    try:
        data[key]["content"] = deserialize_http_message(
            data["path"], data[key], content, interface, key, export_content_files_to
        )
    except:
        status_code: int = data[key]["status_code"]
        if key == "response" and status_code in (HTTPStatus.INTERNAL_SERVER_ERROR, HTTPStatus.REQUEST_TIMEOUT):
            # backend may respond 500, while giving application/x-protobuf as content-type
            # deserialize_http_message() will fail, but it cannot be considered as an
            # internal error, we only log it, and do not store anything in traceback
            logger.exception(f"Error {status_code} in response in {data['log_filename']}, preventing deserialization")
            data[key]["content"] = repr(content)
        else:
            logger.exception(f"Error while deserializing {key} in {data['log_filename']}")
            data[key]["raw_content"] = str(content)
            data[key]["traceback"] = str(traceback.format_exc())


# if __name__ == "__main__":
#     content = json.load(open("logs/interfaces/library/005__v0.5_traces.json"))["request"]["content"]
#     print(json.dumps(_decode_v_0_5_traces(content), indent=2))
