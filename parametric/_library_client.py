import contextlib
import urllib.parse
import time

from typing import Generator
from typing import List
from typing import Optional
from typing import Tuple
from typing import TypedDict

import grpc
import requests

from parametric.protos import apm_test_client_pb2 as pb
from parametric.protos import apm_test_client_pb2_grpc


class StartSpanResponse(TypedDict):
    span_id: int
    trace_id: int


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
    ) -> StartSpanResponse:
        raise NotImplementedError

    def finish_span(self, span_id: int) -> None:
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


class APMLibraryClientHTTP(APMLibraryClient):
    def __init__(self, url: str, timeout: int):
        self._base_url = url
        self._session = requests.Session()

        # wait for server to start
        self._wait(timeout)

    def _wait(self, timeout):
        delay = 0.01
        for i in range(int(timeout / delay)):
            try:
                resp = self._session.get(self._url("/non-existent-endpoint-to-ping-until-the-server-starts"))
                if resp.status_code == 404:
                    break
            except Exception:
                pass
            time.sleep(delay)
        else:
            raise RuntimeError("Timeout of %s seconds exceeded waiting for HTTP server to start" % timeout)

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
            },
        )
        resp_json = resp.json()
        return StartSpanResponse(span_id=resp_json["span_id"], trace_id=resp_json["trace_id"],)

    def finish_span(self, span_id: int) -> None:
        self._session.post(self._url("/trace/span/finish"), json={"span_id": span_id,})
        return None

    def span_set_meta(self, span_id: int, key: str, value: str) -> None:
        self._session.post(self._url("/trace/span/set_meta"), json={"span_id": span_id, "key": key, "value": value,})

    def span_set_metric(self, span_id: int, key: str, value: float) -> None:
        self._session.post(self._url("/trace/span/set_metric"), json={"span_id": span_id, "key": key, "value": value,})

    def span_set_error(self, span_id: int, typestr: str, message: str, stack: str) -> None:
        self._session.post(
            self._url("/trace/span/error"),
            json={"span_id": span_id, "type": typestr, "message": message, "stack": stack},
        )

    def trace_inject_headers(self, span_id):
        resp = self._session.post(self._url("/trace/span/inject_headers"), json={"span_id": span_id},)
        return resp.json()["http_headers"]

    def trace_flush(self) -> None:
        self._session.post(self._url("/trace/span/flush"), json={})
        self._session.post(self._url("/trace/stats/flush"), json={})


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

    def finish(self):
        self._client.finish_span(self.span_id)


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
    ):
        distributed_message = pb.DistributedHTTPHeaders()
        for key, value in http_headers:
            distributed_message.http_headers[key] = value

        resp = self._client.StartSpan(
            pb.StartSpanArgs(
                name=name,
                service=service,
                resource=resource,
                parent_id=parent_id,
                type=typestr,
                origin=origin,
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
        return [(k, v) for k, v in resp.http_headers.http_headers.items()]

    def stop(self):
        return self._client.StopTracer(pb.StopTracerArgs())

    def span_set_meta(self, span_id: int, key: str, val: str):
        self._client.SpanSetMeta(pb.SpanSetMetaArgs(span_id=span_id, key=key, value=val,))

    def span_set_metric(self, span_id: int, key: str, val: float):
        self._client.SpanSetMetric(pb.SpanSetMetricArgs(span_id=span_id, key=key, value=val,))

    def span_set_error(self, span_id: int, typestr: str = "", message: str = "", stack: str = ""):
        self._client.SpanSetError(pb.SpanSetErrorArgs(span_id=span_id, type=typestr, message=message, stack=stack))

    def finish_span(self, span_id: int):
        self._client.FinishSpan(pb.FinishSpanArgs(id=span_id))


class APMLibrary:
    def __init__(self, client: APMLibraryClient):
        self._client = client

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
    ) -> Generator[_TestSpan, None, None]:
        resp = self._client.trace_start_span(
            name=name,
            service=service,
            resource=resource,
            parent_id=parent_id,
            typestr=typestr,
            origin=origin,
            http_headers=http_headers if http_headers is not None else [],
        )
        span = _TestSpan(self._client, resp["span_id"])
        yield span
        span.finish()

    def flush(self):
        self._client.trace_flush()

    def inject_headers(self, span_id) -> List[Tuple[str, str]]:
        return self._client.trace_inject_headers(span_id)
