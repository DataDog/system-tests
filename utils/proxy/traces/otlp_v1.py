from collections.abc import Iterator
from typing import Any


def _flatten_otlp_attributes(attributes: list[dict]) -> Iterator[tuple[str, Any]]:
    for key_value in attributes:
        v = key_value["value"]
        # Use `is not None` rather than truthiness so zero/false/empty values are not skipped.
        if v.get("stringValue") is not None:
            yield key_value["key"], v["stringValue"]
        elif v.get("boolValue") is not None:
            yield key_value["key"], v["boolValue"]
        elif v.get("intValue") is not None:
            yield key_value["key"], v["intValue"]
        elif v.get("doubleValue") is not None:
            yield key_value["key"], v["doubleValue"]
        elif v.get("arrayValue") is not None:
            yield key_value["key"], v["arrayValue"]
        elif v.get("kvlistValue") is not None:
            yield key_value["key"], v["kvlistValue"]
        elif v.get("bytesValue") is not None:
            yield key_value["key"], v["bytesValue"]
        else:
            raise ValueError(f"Unknown attribute value: {v}")


def deserialize_otlp_v1_trace(content: dict) -> dict:
    # Iterate the OTLP payload to flatten any attributes dictionary
    # Attributes are represented in the following way:
    # - {"key": "value": { "stringValue": <VALUE> }}
    # - {"key": "value": { "boolValue": <VALUE> }}
    # - etc.
    #
    # We'll remap them to simple key-value pairs {"key": <VALUE>, "key2": <VALUE2>, etc.}
    for resource_span in content.get("resourceSpans", []):
        resource = resource_span.get("resource", {})
        if resource:
            remapped_attributes = dict(_flatten_otlp_attributes(resource.get("attributes", [])))
            resource["attributes"] = remapped_attributes

        for scope_span in resource_span.get("scopeSpans", []):
            scope = scope_span.get("scope", {})
            scope_attributes = scope.get("attributes", [])
            if scope and scope_attributes:
                remapped_attributes = dict(_flatten_otlp_attributes(scope_attributes))
                scope["attributes"] = remapped_attributes

            for span in scope_span.get("spans", []):
                span_attributes = span.get("attributes", [])
                if span_attributes:
                    remapped_attributes = dict(_flatten_otlp_attributes(span_attributes))
                    span["attributes"] = remapped_attributes

                for event in span.get("events", []):
                    event_attributes = event.get("attributes", [])
                    if event_attributes:
                        remapped_attributes = dict(_flatten_otlp_attributes(event_attributes))
                        event["attributes"] = remapped_attributes

                for link in span.get("links", []):
                    link_attributes = link.get("attributes", [])
                    if link_attributes:
                        remapped_attributes = dict(_flatten_otlp_attributes(link_attributes))
                        link["attributes"] = remapped_attributes

    return content
