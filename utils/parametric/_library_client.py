# pylint: disable=E1101
import contextlib
import time
import urllib.parse
from typing import Generator
from typing import List
from typing import Optional
from typing import Tuple
from typing import TypedDict

import grpc
import requests

from utils.parametric.protos import apm_test_client_pb2 as pb
from utils.parametric.protos import apm_test_client_pb2_grpc
from utils.parametric.spec.otel_trace import OtelSpanContext
from utils.parametric.spec.otel_trace import convert_to_proto


class StartSpanResponse(TypedDict):
    span_id: int
    trace_id: int


class Link(TypedDict):
    parent_id: int  # 0 to extract from headers
    attributes: dict


class APMLibraryClient:
    def trace_start_span(
        self,
        name: str,
        service: str,
        resource: str,
        parent_id: int,
        typestr: str,
        origin: str,
        http_headers: List[Tuple[str, str]],
        links: List[Link],
    ) -> StartSpanResponse:
        raise NotImplementedError

    def otel_trace_start_span(
        self,
        name: str,
        timestamp: int,
        span_kind: int,
        parent_id: int,
        http_headers: List[Tuple[str, str]],
        attributes: dict = None,
    ) -> StartSpanResponse:
        raise NotImplementedError

    def finish_span(self, span_id: int) -> None:
        raise NotImplementedError

    def otel_end_span(self, span_id: int, timestamp: int) -> None:
        raise NotImplementedError

    def otel_set_attributes(self, span_id: int, attributes: dict) -> None:
        raise NotImplementedError

    def otel_set_name(self, span_id: int, name: str) -> None:
        raise NotImplementedError

    def otel_set_status(self, span_id: int, code: int, description: str) -> None:
        raise NotImplementedError

    def otel_is_recording(self, span_id: int) -> bool:
        raise NotImplementedError

    def otel_get_span_context(self, span_id: int):
        raise NotImplementedError

    def span_add_link(self, span_id: int, parent_id: int, attributes: dict) -> None:
        raise NotImplementedError

    def span_set_meta(self, span_id: int, key: str, value: str) -> None:
        raise NotImplementedError

    def span_set_metric(self, span_id: int, key: str, value: float) -> None:
        raise NotImplementedError

    def span_set_error(self, span_id: int, typestr: str, message: str, stack: str) -> None:
        raise NotImplementedError

    def trace_inject_headers(self, span_id) -> List[Tuple[str, str]]:
        raise NotImplementedError

    def trace_flush(self) -> None:
        raise NotImplementedError

    def trace_stop(self) -> None:
        raise NotImplementedError

    def otel_flush(self, timeout: int) -> bool:
        raise NotImplementedError

    def http_request(self, method: str, url: str, headers: List[Tuple[str, str]]) -> None:
        raise NotImplementedError


class APMLibraryClientHTTP(APMLibraryClient):
    def __init__(self, url: str, timeout: int):
        self._base_url = url
        self._session = requests.Session()

        # wait for server to start
        self._wait(timeout)

    def _wait(self, timeout):
        delay = 0.01
        for _ in range(int(timeout / delay)):
            try:
                resp = self._session.get(self._url("/non-existent-endpoint-to-ping-until-the-server-starts"))
                if resp.status_code == 404:
                    break
            except Exception:
                pass
            time.sleep(delay)
        else:
            raise RuntimeError(f"Timeout of {timeout} seconds exceeded waiting for HTTP server to start")

    def _url(self, path: str) -> str:
        return urllib.parse.urljoin(self._base_url, path)

    def trace_start_span(
        self,
        name: str,
        service: str,
        resource: str,
        parent_id: int,
        typestr: str,
        origin: str,
        http_headers: Optional[List[Tuple[str, str]]],
        links: Optional[List[Link]],
    ):
        resp = self._session.post(
            self._url("/trace/span/start"),
            json={
                "name": name,
                "service": service,
                "resource": resource,
                "parent_id": parent_id,
                "type": typestr,
                "origin": origin,
                "http_headers": http_headers,
                "links": links,
            },
        )
        resp_json = resp.json()
        return StartSpanResponse(span_id=resp_json["span_id"], trace_id=resp_json["trace_id"],)

    def finish_span(self, span_id: int) -> None:
        self._session.post(self._url("/trace/span/finish"), json={"span_id": span_id,})

    def span_set_meta(self, span_id: int, key: str, value: str) -> None:
        self._session.post(self._url("/trace/span/set_meta"), json={"span_id": span_id, "key": key, "value": value,})

    def span_set_metric(self, span_id: int, key: str, value: float) -> None:
        self._session.post(self._url("/trace/span/set_metric"), json={"span_id": span_id, "key": key, "value": value,})

    def span_set_error(self, span_id: int, typestr: str, message: str, stack: str) -> None:
        self._session.post(
            self._url("/trace/span/error"),
            json={"span_id": span_id, "type": typestr, "message": message, "stack": stack},
        )

    def span_add_link(self, span_id: int, parent_id: int, attributes: dict = None) -> None:
        self._session.post(
            self._url("/trace/span/add_link"),
            json={"span_id": span_id, "parent_id": parent_id, "attributes": attributes or {}},
        )

    def trace_inject_headers(self, span_id):
        resp = self._session.post(self._url("/trace/span/inject_headers"), json={"span_id": span_id},)
        return resp.json()["http_headers"]

    def trace_flush(self) -> None:
        self._session.post(self._url("/trace/span/flush"), json={})
        self._session.post(self._url("/trace/stats/flush"), json={})

    def otel_trace_start_span(
        self,
        name: str,
        timestamp: int,
        span_kind: int,
        parent_id: int,
        http_headers: List[Tuple[str, str]],
        attributes: dict = None,
    ) -> StartSpanResponse:
        resp = self._session.post(
            self._url("/trace/otel/start_span"),
            json={
                "name": name,
                "timestamp": timestamp,
                "span_kind": span_kind,
                "parent_id": parent_id,
                "http_headers": http_headers,
                "attributes": attributes or {},
            },
        ).json()
        return StartSpanResponse(span_id=resp["span_id"], trace_id=resp["trace_id"])

    def otel_end_span(self, span_id: int, timestamp: int) -> None:
        self._session.post(self._url("/trace/otel/end_span"), json={"id": span_id, "timestamp": timestamp})

    def otel_set_attributes(self, span_id: int, attributes) -> None:
        self._session.post(self._url("/trace/otel/set_attributes"), json={"span_id": span_id, "attributes": attributes})

    def otel_set_name(self, span_id: int, name: str) -> None:
        self._session.post(self._url("/trace/otel/set_name"), json={"span_id": span_id, "name": name})

    def otel_set_status(self, span_id: int, code: int, description: str) -> None:
        self._session.post(
            self._url("/trace/otel/set_status"), json={"span_id": span_id, "code": code, "description": description}
        )

    def otel_is_recording(self, span_id: int) -> bool:
        resp = self._session.post(self._url("/trace/otel/is_recording"), json={"span_id": span_id}).json()
        return resp["is_recording"]

    def otel_get_span_context(self, span_id: int):
        resp = self._session.post(self._url("/trace/otel/span_context"), json={"span_id": span_id}).json()
        return OtelSpanContext(
            trace_id=resp["trace_id"],
            span_id=resp["span_id"],
            trace_flags=resp["trace_flags"],
            trace_state=resp["trace_state"],
            remote=resp["remote"],
        )

    def otel_flush(self, timeout: int) -> bool:
        resp = self._session.post(self._url("/trace/otel/flush"), json={"seconds": timeout}).json()
        return resp["success"]


class _TestSpan:
    def __init__(self, client: APMLibraryClient, span_id: int):
        self._client = client
        self.span_id = span_id

    def set_meta(self, key: str, val: str):
        self._client.span_set_meta(self.span_id, key, val)

    def set_metric(self, key: str, val: float):
        self._client.span_set_metric(self.span_id, key, val)

    def set_error(self, typestr: str = "", message: str = "", stack: str = ""):
        self._client.span_set_error(self.span_id, typestr, message, stack)

    def add_link(self, parent_id: int, attributes: dict = None):
        self._client.span_add_link(self.span_id, parent_id, attributes)

    def finish(self):
        self._client.finish_span(self.span_id)


class _TestOtelSpan:
    def __init__(self, client: APMLibraryClient, span_id: int):
        self._client = client
        self.span_id = span_id

    def set_attributes(self, attributes):
        self._client.otel_set_attributes(self.span_id, attributes)

    def set_name(self, name):
        self._client.otel_set_name(self.span_id, name)

    def set_status(self, code, description):
        self._client.otel_set_status(self.span_id, code, description)

    def end_span(self, timestamp: int = 0):
        self._client.otel_end_span(self.span_id, timestamp)

    def is_recording(self) -> bool:
        return self._client.otel_is_recording(self.span_id)

    def span_context(self) -> OtelSpanContext:
        return self._client.otel_get_span_context(self.span_id)


class APMLibraryClientGRPC:
    def __init__(self, url: str, timeout: int):
        channel = grpc.insecure_channel(url)
        grpc.channel_ready_future(channel).result(timeout=timeout)
        client = apm_test_client_pb2_grpc.APMClientStub(channel)
        self._client = client

    def __enter__(self) -> "APMLibrary":
        return self

    def trace_start_span(
        self,
        name: str,
        service: str,
        resource: str,
        parent_id: int,
        typestr: str,
        origin: str,
        http_headers: List[Tuple[str, str]],
        links: List[Link],
    ):
        distributed_message = pb.DistributedHTTPHeaders()
        for key, value in http_headers:
            distributed_message.http_headers.append(pb.HeaderTuple(key=key, value=value))

        pb_links = []
        for link in links:
            pb_link = pb.SpanLink()
            pb_link.parent_id = link["parent_id"]
            pb_link.attributes = convert_to_proto(link["attributes"])
            pb_links.append(pb_link)

        resp = self._client.StartSpan(
            pb.StartSpanArgs(
                name=name,
                service=service,
                resource=resource,
                parent_id=parent_id,
                type=typestr,
                origin=origin,
                http_headers=distributed_message,
                span_links=pb_links,
            )
        )
        return {
            "span_id": resp.span_id,
            "trace_id": resp.trace_id,
        }

    def otel_trace_start_span(
        self,
        name: str,
        timestamp: int,
        span_kind: int,
        parent_id: int,
        http_headers: List[Tuple[str, str]],
        attributes: dict = None,
    ):
        distributed_message = pb.DistributedHTTPHeaders()
        for key, value in http_headers:
            distributed_message.http_headers.append(pb.HeaderTuple(key=key, value=value))

        resp = self._client.OtelStartSpan(
            pb.OtelStartSpanArgs(
                name=name,
                timestamp=timestamp,
                span_kind=span_kind,
                parent_id=parent_id,
                attributes=convert_to_proto(attributes),
                http_headers=distributed_message,
            )
        )
        return {
            "span_id": resp.span_id,
            "trace_id": resp.trace_id,
        }

    def trace_flush(self):
        self._client.FlushSpans(pb.FlushSpansArgs())
        self._client.FlushTraceStats(pb.FlushTraceStatsArgs())

    def trace_inject_headers(self, span_id) -> List[Tuple[str, str]]:
        resp = self._client.InjectHeaders(pb.InjectHeadersArgs(span_id=span_id,))
        return [(header_tuple.key, header_tuple.value) for header_tuple in resp.http_headers.http_headers]

    def stop(self):
        return self._client.StopTracer(pb.StopTracerArgs())

    def span_set_meta(self, span_id: int, key: str, val: str):
        self._client.SpanSetMeta(pb.SpanSetMetaArgs(span_id=span_id, key=key, value=val,))

    def span_set_metric(self, span_id: int, key: str, val: float):
        self._client.SpanSetMetric(pb.SpanSetMetricArgs(span_id=span_id, key=key, value=val,))

    def span_set_error(self, span_id: int, typestr: str = "", message: str = "", stack: str = ""):
        self._client.SpanSetError(pb.SpanSetErrorArgs(span_id=span_id, type=typestr, message=message, stack=stack))

    def span_add_link(self, span_id: int, parent_id: int, attributes: dict) -> None:
        self._client.SpanAddLink(
            pb.SpanAddLinkArgs(span_id=span_id, parent_id=parent_id, attributes=convert_to_proto(attributes))
        )

    def finish_span(self, span_id: int):
        self._client.FinishSpan(pb.FinishSpanArgs(id=span_id))

    def http_client_request(self, method: str, url: str, headers: List[Tuple[str, str]], body: bytes) -> int:
        hs = pb.DistributedHTTPHeaders()
        for key, value in headers:
            hs.http_headers.append(pb.HeaderTuple(key=key, value=value))

        self._client.HTTPClientRequest(pb.HTTPRequestArgs(method=method, url=url, headers=hs, body=body,))

    def otel_end_span(self, span_id: int, timestamp: int):
        self._client.OtelEndSpan(pb.OtelEndSpanArgs(id=span_id, timestamp=timestamp))

    def otel_set_attributes(self, span_id: int, attributes):
        self._client.OtelSetAttributes(
            pb.OtelSetAttributesArgs(span_id=span_id, attributes=convert_to_proto(attributes))
        )

    def otel_set_name(self, span_id: int, name: str):
        self._client.OtelSetName(pb.OtelSetNameArgs(span_id=span_id, name=name))

    def otel_set_status(self, span_id: int, code: int, description: str):
        self._client.OtelSetStatus(pb.OtelSetStatusArgs(span_id=span_id, code=code, description=description))

    def otel_is_recording(self, span_id: int) -> bool:
        return self._client.OtelIsRecording(pb.OtelIsRecordingArgs(span_id=span_id)).is_recording

    def otel_get_span_context(self, span_id: int):
        sctx = self._client.OtelSpanContext(pb.OtelSpanContextArgs(span_id=span_id))
        return OtelSpanContext(
            trace_id=sctx.trace_id,
            span_id=sctx.span_id,
            trace_flags=sctx.trace_flags,
            trace_state=sctx.trace_state,
            remote=sctx.remote,
        )

    def otel_flush(self, timeout: int) -> bool:
        return self._client.OtelFlushSpans(pb.OtelFlushSpansArgs(seconds=timeout)).success


class APMLibrary:
    def __init__(self, client: APMLibraryClient, lang):
        self._client = client
        self.lang = lang

    def __enter__(self) -> "APMLibrary":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Only attempt a flush if there was no exception raised.
        if exc_type is None:
            self.flush()

    @contextlib.contextmanager
    def start_span(
        self,
        name: str,
        service: str = "",
        resource: str = "",
        parent_id: int = 0,
        typestr: str = "",
        origin: str = "",
        http_headers: Optional[List[Tuple[str, str]]] = None,
        links: Optional[List[Link]] = None,
    ) -> Generator[_TestSpan, None, None]:
        resp = self._client.trace_start_span(
            name=name,
            service=service,
            resource=resource,
            parent_id=parent_id,
            typestr=typestr,
            origin=origin,
            http_headers=http_headers if http_headers is not None else [],
            links=links if links is not None else [],
        )
        span = _TestSpan(self._client, resp["span_id"])
        yield span
        span.finish()

    @contextlib.contextmanager
    def otel_start_span(
        self,
        name: str,
        timestamp: int = 0,
        span_kind: int = 0,
        parent_id: int = 0,
        attributes: dict = None,
        http_headers: Optional[List[Tuple[str, str]]] = None,
    ) -> Generator[_TestOtelSpan, None, None]:
        resp = self._client.otel_trace_start_span(
            name=name,
            timestamp=timestamp,
            span_kind=span_kind,
            parent_id=parent_id,
            attributes=attributes,
            http_headers=http_headers if http_headers is not None else [],
        )
        span = _TestOtelSpan(self._client, resp["span_id"])
        yield span

        return {
            "span_id": resp["span_id"],
            "trace_id": resp["trace_id"],
        }

    def flush(self):
        self._client.trace_flush()

    def otel_flush(self, timeout_sec: int) -> bool:
        return self._client.otel_flush(timeout_sec)

    def inject_headers(self, span_id) -> List[Tuple[str, str]]:
        return self._client.trace_inject_headers(span_id)

    def http_client_request(
        self, url: str, method: str = "GET", headers: List[Tuple[str, str]] = None, body: Optional[bytes] = b"",
    ):
        """Do an HTTP request with the given method and headers."""
        return self._client.http_client_request(method=method, url=url, headers=headers or [], body=body,)
