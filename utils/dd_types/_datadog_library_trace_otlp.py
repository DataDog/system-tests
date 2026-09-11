# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""OTLP-to-Datadog span adapter.

Wraps OTLP spans (as captured by interfaces.open_telemetry) into the same
DataDogLibraryTrace / DataDogLibrarySpan interface used by the library
interface validator. This allows existing AppSec tests to work unchanged
when traces are exported via OTLP instead of the Datadog agent protocol.
"""

import base64
import json
from typing import Any

from ._datadog_library_trace import DataDogLibrarySpan, DataDogLibraryTrace
from ._utils import get_rid_from_span_data

# Keys whose values are numeric in Datadog format but string in OTLP.
# We coerce these back to numbers so assertions like `== 1` work.
_NUMERIC_METRIC_KEYS = {
    "_dd.appsec.enabled",
    "_dd.appsec.waf.duration",
    "_dd.appsec.waf.duration_ext",
    "_dd.appsec.event_rules.error_count",
    "_dd.appsec.event_rules.loaded",
    "_dd.appsec.trace.integer",
    "_dd.top_level",
    "_dd.measured",
    "_sampling_priority_v1",
    "_sampling.priority_v1",
    "_sampling.priority",
}

# Keys whose values are base64-encoded appsec trigger data that need decoding.
_APPSEC_DATA_KEYS = {"appsec", "_dd.appsec.json", "iast", "_dd.iast.json"}


def _try_decode_appsec(value: Any) -> Any:  # noqa: ANN401
    """Decode base64-encoded appsec data (msgpack or JSON) into a dict."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return value
    try:
        decoded_bytes = base64.b64decode(value)
    except Exception:
        return value
    # Try JSON first
    try:
        return json.loads(decoded_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    # Try msgpack
    try:
        import msgpack  # noqa: PLC0415

        return msgpack.unpackb(decoded_bytes, raw=False)
    except ImportError:
        pass
    # Fallback: return the raw decoded text
    try:
        text = decoded_bytes.decode("utf-8", errors="replace")
        if "triggers" in text:
            return {"_raw": text}
        return value
    except Exception:
        return value


def _coerce_numeric(key: str, value: Any) -> Any:  # noqa: ANN401
    """Coerce string values to numbers for known numeric metric keys."""
    if key not in _NUMERIC_METRIC_KEYS:
        return value
    if isinstance(value, str):
        try:
            f = float(value)
            return int(f) if f == int(f) else f
        except ValueError:
            return value
    return value


class DataDogLibrarySpanOTLP(DataDogLibrarySpan):
    """Wraps a single OTLP span into the DataDogLibrarySpan interface.

    OTLP spans store all data in a flat ``attributes`` dict. This adapter
    maps ``meta``, ``meta_struct``, and ``metrics`` to that same dict so
    that existing assertions like ``span["meta"]["_dd.appsec.json"]``
    or ``span.get("meta_struct", {}).get("appsec")`` work as expected.

    Key transformations:
    - Numeric string values (e.g. ``"1"``) are coerced to ints for known metric keys
    - Base64-encoded appsec data (the ``appsec`` and ``_dd.appsec.json`` keys) is
      decoded into dicts so tests can access ``span["meta"]["appsec"]["triggers"]``
    """

    def __init__(self, trace: "DataDogLibraryTraceOTLP", raw_span: dict, resource_attributes: dict | None = None):
        self.trace = trace
        self.raw_span = raw_span
        self._resource_attributes = resource_attributes or {}

    def _merged_attributes(self) -> dict[str, Any]:
        """Merge span-level and resource-level attributes, with type coercion."""
        attrs = self.raw_span.get("attributes", {})
        if isinstance(attrs, list):
            attrs = {a["key"]: a.get("value") for a in attrs if isinstance(a, dict) and "key" in a}
        result = dict(self._resource_attributes)
        result.update(attrs)
        return result

    def _meta_dict(self) -> dict[str, Any]:
        """Build the meta dict with appsec data decoded and numerics coerced."""
        attrs = self._merged_attributes()
        result = {}
        for key, value in attrs.items():
            if key in _APPSEC_DATA_KEYS:
                result[key] = _try_decode_appsec(value)
            else:
                result[key] = _coerce_numeric(key, value)
        return result

    def _metrics_dict(self) -> dict[str, Any]:
        """Build the metrics dict with numeric coercion.

        In Datadog format, metrics are always numeric. In OTLP, all attributes
        are strings. We coerce any string that looks like a number to int/float.
        """
        attrs = self._merged_attributes()
        result = {}
        for key, value in attrs.items():
            if isinstance(value, str):
                # Try to coerce numeric strings to numbers
                try:
                    f = float(value)
                    result[key] = int(f) if f == int(f) else f
                except ValueError:
                    result[key] = value  # type: ignore[assignment]
            else:
                result[key] = _coerce_numeric(key, value)
        return result

    def __contains__(self, key: str) -> bool:
        if key in ("meta", "meta_struct", "metrics"):
            return True
        if key == "trace_id":
            return True
        if key == "span_id":
            return "spanId" in self.raw_span or "span_id" in self.raw_span
        if key == "parent_id":
            return "parentSpanId" in self.raw_span or "parent_span_id" in self.raw_span
        if key == "name":
            return "name" in self.raw_span
        if key == "type":
            return "attributes" in self.raw_span
        if key == "start":
            return "startTimeUnixNano" in self.raw_span or "start_time_unix_nano" in self.raw_span
        if key == "duration":
            return "startTimeUnixNano" in self.raw_span and "endTimeUnixNano" in self.raw_span
        return key in self.raw_span

    def get(self, key: str, default: Any = None):  # noqa: ANN401
        if key == "trace_id":
            return self.trace.trace_id
        if key == "span_id":
            return self.raw_span.get("spanId", self.raw_span.get("span_id", default))
        if key == "parent_id":
            return self.raw_span.get("parentSpanId", self.raw_span.get("parent_span_id", default))
        if key == "name":
            return self.raw_span.get("name", default)
        if key == "type":
            return self._merged_attributes().get("span.type", default)
        if key == "service":
            # OTLP stores service name in resource attributes as "service.name"
            return self._merged_attributes().get("service.name", default)
        if key == "start":
            return int(self.raw_span.get("startTimeUnixNano", self.raw_span.get("start_time_unix_nano", 0)))
        if key == "duration":
            start = int(self.raw_span.get("startTimeUnixNano", 0))
            end = int(self.raw_span.get("endTimeUnixNano", 0))
            return end - start
        if key in ("meta", "meta_struct"):
            return self._meta_dict()
        if key == "metrics":
            return self._metrics_dict()
        return self.raw_span.get(key, default)

    def __getitem__(self, key: str):
        value = self.get(key, KeyError)
        if value is KeyError:
            raise KeyError(key)
        return value

    @property
    def meta(self) -> dict[str, Any]:
        return self._meta_dict()

    @property
    def metrics(self) -> dict[str, Any]:
        return self._metrics_dict()

    def get_rid(self) -> str | None:
        attrs = self._merged_attributes()
        return get_rid_from_span_data(
            attrs.get("span.type", ""),
            attrs,
            attrs,
        )

    def get_sampling_priority(self) -> int | None:
        attrs = self._merged_attributes()
        val = attrs.get("_sampling_priority_v1") or attrs.get("_sampling.priority_v1")
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                return None
        return None

    def get_span_links(self):
        return []


class DataDogLibraryTraceOTLP(DataDogLibraryTrace):
    """Wraps OTLP trace data (resourceSpans) into the DataDogLibraryTrace interface."""

    def __init__(self, data: dict, resource_span: dict):
        self.data = data
        self.raw_trace = resource_span
        self.format = "otlp"  # type: ignore[assignment]

        resource_attrs = resource_span.get("resource", {}).get("attributes", {})
        if isinstance(resource_attrs, list):
            resource_attrs = {a["key"]: a.get("value") for a in resource_attrs if isinstance(a, dict) and "key" in a}

        spans: list[DataDogLibrarySpan] = []
        for scope_span in resource_span.get("scopeSpans", []):
            for raw_span in scope_span.get("spans", []):
                spans.append(DataDogLibrarySpanOTLP(self, raw_span, resource_attrs))
        self.spans = spans

    @property
    def trace_id(self) -> str | int:
        if self.spans:
            raw = self.spans[0].raw_span
            return raw.get("traceId", raw.get("trace_id", ""))
        return ""

    @property
    def trace_id_as_int(self) -> int:
        tid = self.trace_id
        if isinstance(tid, str) and tid:
            return int(tid, 16) & 0xFFFFFFFFFFFFFFFF
        if isinstance(tid, int):
            return tid
        return 0
