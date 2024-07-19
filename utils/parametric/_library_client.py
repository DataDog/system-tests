# pylint: disable=E1101
import contextlib
import time
import urllib.parse
from typing import Generator, List, Optional, Tuple, TypedDict, Union, Dict

from docker.models.containers import Container
import grpc
import pytest
import requests

from utils.parametric.protos import apm_test_client_pb2 as pb
from utils.parametric.protos import apm_test_client_pb2_grpc
from utils.parametric.spec.otel_trace import OtelSpanContext, convert_to_proto
from utils.tools import logger


class StartSpanResponse(TypedDict):
    span_id: int
    trace_id: int


class SpanResponse(TypedDict):
    span_id: int
    trace_id: int


class Link(TypedDict):
    parent_id: int  # 0 to extract from headers
    attributes: dict
    http_headers: List[Tuple[str, str]]


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
        tags: List[Tuple[str, str]],
    ) -> StartSpanResponse:
        raise NotImplementedError

    def otel_trace_start_span(
        self,
        name: str,
        timestamp: int,
        span_kind: int,
        parent_id: int,
        links: List[Link],
        http_headers: List[Tuple[str, str]],
        attributes: dict = None,
    ) -> StartSpanResponse:
        raise NotImplementedError

    def current_span(self) -> Union[SpanResponse, None]:
        raise NotImplementedError

    def finish_span(self, span_id: int) -> None:
        raise NotImplementedError

    def otel_current_span(self) -> Union[SpanResponse, None]:
        raise NotImplementedError

    def otel_get_attribute(self, span_id: int, key: str):
        raise NotImplementedError

    def otel_get_name(self, span_id: int):
        raise NotImplementedError

    def otel_end_span(self, span_id: int, timestamp: int) -> None:
        raise NotImplementedError

    def otel_get_links(self, span_id: int) -> List[Link]:
        raise NotImplementedError

    def otel_set_attributes(self, span_id: int, attributes: dict) -> None:
        raise NotImplementedError

    def otel_set_name(self, span_id: int, name: str) -> None:
        raise NotImplementedError

    def otel_set_status(self, span_id: int, code: int, description: str) -> None:
        raise NotImplementedError

    def otel_add_event(self, span_id: int, name: str, timestamp: int, attributes: dict) -> None:
        raise NotImplementedError

    def otel_record_exception(self, span_id: int, message: str, attributes: dict) -> None:
        raise NotImplementedError

    def otel_is_recording(self, span_id: int) -> bool:
        raise NotImplementedError

    def otel_get_span_context(self, span_id: int):
        raise NotImplementedError

    def span_add_link(
        self, span_id: int, parent_id: int, attributes: dict, http_headers: List[Tuple[str, str]] = None
    ) -> None:
        raise NotImplementedError

    def span_set_resource(self, span_id: int, resource: str) -> None:
        raise NotImplementedError

    def span_set_meta(self, span_id: int, key: str, value) -> None:
        raise NotImplementedError

    def span_set_metric(self, span_id: int, key: str, value: float) -> None:
        raise NotImplementedError

    def span_set_error(self, span_id: int, typestr: str, message: str, stack: str) -> None:
        raise NotImplementedError

    def span_get_name(self, span_id: int):
        raise NotImplementedError

    def span_get_resource(self, span_id: int):
        raise NotImplementedError

    def span_get_meta(self, span_id: int, key: str):
        raise NotImplementedError

    def span_get_metric(self, span_id: int, key: str):
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

    def get_tracer_config(self) -> Dict[str, Optional[str]]:
        raise NotImplementedError


class APMLibraryClientHTTP(APMLibraryClient):
    def __init__(self, url: str, timeout: int, container: Container):
        self._base_url = url
        self._session = requests.Session()
        self.container = container

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
                self.container.reload()
                if self.container.status != "running":
                    message = f"Container {self.container.name} status is {self.container.status}"
                    raise RuntimeError(message)
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
        tags: Optional[List[Tuple[str, str]]],
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
                "span_tags": tags,
            },
        )

        if resp.status_code != 200:
            raise pytest.fail(f"Failed to start span: {resp.text}", pytrace=False)

        resp_json = resp.json()
        return StartSpanResponse(span_id=resp_json["span_id"], trace_id=resp_json["trace_id"],)

    def current_span(self) -> Union[SpanResponse, None]:
        resp_json = self._session.get(self._url("/trace/span/current")).json()
        if not resp_json:
            return None
        return SpanResponse(span_id=resp_json["span_id"], trace_id=resp_json["trace_id"])

    def finish_span(self, span_id: int) -> None:
        self._session.post(self._url("/trace/span/finish"), json={"span_id": span_id,})

    def span_set_resource(self, span_id: int, resource: str) -> None:
        self._session.post(self._url("/trace/span/set_resource"), json={"span_id": span_id, "resource": resource,})

    def span_set_meta(self, span_id: int, key: str, value) -> None:
        self._session.post(self._url("/trace/span/set_meta"), json={"span_id": span_id, "key": key, "value": value,})

    def span_set_metric(self, span_id: int, key: str, value: float) -> None:
        self._session.post(self._url("/trace/span/set_metric"), json={"span_id": span_id, "key": key, "value": value,})

    def span_set_error(self, span_id: int, typestr: str, message: str, stack: str) -> None:
        self._session.post(
            self._url("/trace/span/error"),
            json={"span_id": span_id, "type": typestr, "message": message, "stack": stack},
        )

    def span_add_link(
        self, span_id: int, parent_id: int, attributes: dict = None, http_headers: List[Tuple[str, str]] = None
    ):
        self._session.post(
            self._url("/trace/span/add_link"),
            json={
                "span_id": span_id,
                "parent_id": parent_id,
                "attributes": attributes or {},
                "http_headers": http_headers or [],
            },
        )

    def span_get_meta(self, span_id: int, key: str):
        resp = self._session.post(self._url("/trace/span/get_meta"), json={"span_id": span_id, "key": key,})
        return resp.json()["value"]

    def span_get_metric(self, span_id: int, key: str):
        resp = self._session.post(self._url("/trace/span/get_metric"), json={"span_id": span_id, "key": key,})
        return resp.json()["value"]

    def span_get_resource(self, span_id: int):
        resp = self._session.post(self._url("/trace/span/get_resource"), json={"span_id": span_id,})
        return resp.json()["resource"]

    def trace_inject_headers(self, span_id):
        resp = self._session.post(self._url("/trace/span/inject_headers"), json={"span_id": span_id},)
        # todo: translate json into list within list
        # so server.xx do not have to
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
        links: List[Link],
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
                "links": links,
                "http_headers": http_headers,
                "attributes": attributes or {},
            },
        ).json()
        return StartSpanResponse(span_id=resp["span_id"], trace_id=resp["trace_id"])

    def otel_current_span(self) -> Union[SpanResponse, None]:
        resp = self._session.get(self._url("/trace/otel/current_span"), json={})
        if not resp:
            return None

        resp_json = resp.json()
        return SpanResponse(span_id=resp_json["span_id"], trace_id=resp_json["trace_id"])

    def otel_get_attribute(self, span_id: int, key: str):
        resp = self._session.post(self._url("/trace/otel/get_attribute"), json={"span_id": span_id, "key": key,})
        return resp.json()["value"]

    def otel_get_name(self, span_id: int):
        resp = self._session.post(self._url("/trace/otel/get_name"), json={"span_id": span_id,})
        return resp.json()["name"]

    def otel_end_span(self, span_id: int, timestamp: int) -> None:
        self._session.post(self._url("/trace/otel/end_span"), json={"id": span_id, "timestamp": timestamp})

    def otel_get_links(self, span_id: int):
        resp_json = self._session.post(self._url("/trace/otel/get_links"), json={"span_id": span_id}).json()

        return resp_json["links"]

    def otel_set_attributes(self, span_id: int, attributes) -> None:
        self._session.post(self._url("/trace/otel/set_attributes"), json={"span_id": span_id, "attributes": attributes})

    def otel_set_name(self, span_id: int, name: str) -> None:
        self._session.post(self._url("/trace/otel/set_name"), json={"span_id": span_id, "name": name})

    def otel_set_status(self, span_id: int, code: int, description: str) -> None:
        self._session.post(
            self._url("/trace/otel/set_status"), json={"span_id": span_id, "code": code, "description": description}
        )

    def otel_add_event(self, span_id: int, name: str, timestamp: int, attributes) -> None:
        self._session.post(
            self._url("/trace/otel/add_event"),
            json={"span_id": span_id, "name": name, "timestamp": timestamp, "attributes": attributes},
        )

    def otel_record_exception(self, span_id: int, message: str, attributes) -> None:
        self._session.post(
            self._url("/trace/otel/record_exception"),
            json={"span_id": span_id, "message": message, "attributes": attributes},
        )

    def otel_is_recording(self, span_id: int) -> bool:
        resp = self._session.post(self._url("/trace/otel/is_recording"), json={"span_id": span_id}).json()
        return resp["is_recording"]

    def otel_get_span_context(self, span_id: int) -> OtelSpanContext:
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

    def http_client_request(self, method: str, url: str, headers: List[Tuple[str, str]], body: bytes) -> int:
        resp = self._session.post(
            self._url("/http/client/request"),
            json={"method": method, "url": url, "headers": headers or [], "body": body.decode()},
        ).json()
        return resp

    def get_tracer_config(self) -> Dict[str, Optional[str]]:
        resp = self._session.get(self._url("/trace/config")).json()
        config_dict = resp["config"]
        return {
            "dd_service": config_dict.get("dd_service", None),
            "dd_log_level": config_dict.get("dd_log_level", None),
            "dd_trace_sample_rate": config_dict.get("dd_trace_sample_rate", None),
            "dd_trace_enabled": config_dict.get("dd_trace_enabled", None),
            "dd_runtime_metrics_enabled": config_dict.get("dd_runtime_metrics_enabled", None),
            "dd_tags": config_dict.get("dd_tags", None),
            "dd_trace_propagation_style": config_dict.get("dd_trace_propagation_style", None),
            "dd_trace_debug": config_dict.get("dd_trace_debug", None),
            "dd_trace_otel_enabled": config_dict.get("dd_trace_otel_enabled", None),
            "dd_trace_sample_ignore_parent": config_dict.get("dd_trace_sample_ignore_parent", None),
            "dd_env": config_dict.get("dd_env", None),
            "dd_version": config_dict.get("dd_version", None),
        }


class _TestSpan:
    def __init__(self, client: APMLibraryClient, span_id: int, trace_id: int = 0, parent_id: int = 0):
        self._client = client
        self.span_id = span_id
        self.trace_id = trace_id

    def set_resource(self, resource: str):
        self._client.span_set_resource(self.span_id, resource)

    def set_meta(self, key: str, val):
        self._client.span_set_meta(self.span_id, key, val)

    def set_metric(self, key: str, val: float):
        self._client.span_set_metric(self.span_id, key, val)

    def set_error(self, typestr: str = "", message: str = "", stack: str = ""):
        self._client.span_set_error(self.span_id, typestr, message, stack)

    def add_link(self, parent_id: int, attributes: dict = None, http_headers: List[Tuple[str, str]] = None):
        self._client.span_add_link(self.span_id, parent_id, attributes, http_headers)

    def get_name(self):
        return self._client.span_get_name(self.span_id)

    def get_resource(self):
        return self._client.span_get_resource(self.span_id)

    def get_meta(self, key: str):
        return self._client.span_get_meta(self.span_id, key)

    def get_metric(self, key: str):
        return self._client.span_get_metric(self.span_id, key)

    def finish(self):
        self._client.finish_span(self.span_id)


class _TestOtelSpan:
    def __init__(self, client: APMLibraryClient, span_id: int, trace_id: int = 0):
        self._client = client
        self.span_id = span_id
        self.trace_id = trace_id

    # API methods

    def set_attributes(self, attributes):
        self._client.otel_set_attributes(self.span_id, attributes)

    def set_attribute(self, key, value):
        self._client.otel_set_attributes(self.span_id, {key: value})

    def set_name(self, name):
        self._client.otel_set_name(self.span_id, name)

    def set_status(self, code, description):
        self._client.otel_set_status(self.span_id, code, description)

    def add_event(self, name: str, timestamp: Optional[int] = None, attributes: Optional[dict] = None):
        self._client.otel_add_event(self.span_id, name, timestamp, attributes)

    def record_exception(self, message: str, attributes: Optional[dict] = None):
        self._client.otel_record_exception(self.span_id, message, attributes)

    def end_span(self, timestamp: int = 0):
        self._client.otel_end_span(self.span_id, timestamp)

    def is_recording(self) -> bool:
        return self._client.otel_is_recording(self.span_id)

    def span_context(self) -> OtelSpanContext:
        return self._client.otel_get_span_context(self.span_id)

    # SDK methods

    def get_attribute(self, key: str):
        return self._client.otel_get_attribute(self.span_id, key)

    def get_name(self):
        return self._client.otel_get_name(self.span_id)

    def get_links(self):
        return self._client.otel_get_links(self.span_id)


class APMLibraryClientGRPC:
    def __init__(self, url: str, timeout: int, container: Container):
        self.container = container

        channel = grpc.insecure_channel(url)
        try:
            grpc.channel_ready_future(channel).result(timeout=timeout)
        except grpc.FutureTimeoutError:
            container.reload()
            logs = container.logs().decode("utf-8")
            logger.error("gRPC timeout, stopping test.")
            logger.error(f"Container {container.name} status is: {container.status}. Logs:\n{logs}")

            raise RuntimeError(f"Container {container.name} did not respond to gRPC request")

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
        tags: List[Tuple[str, str]],
    ):
        distributed_message = pb.DistributedHTTPHeaders()
        for key, value in http_headers:
            distributed_message.http_headers.append(pb.HeaderTuple(key=key, value=value))

        pb_tags = []
        for key, value in tags:
            pb_tags.append(pb.HeaderTuple(key=key, value=value))

        pb_links = []
        for link in links:
            pb_link = pb.SpanLink(attributes=convert_to_proto(link.get("attributes")))
            if link.get("parent_id") and link.get("http_headers"):
                raise ValueError("Link cannot have both parent_id and http_headers")
            if link.get("parent_id"):
                pb_link.parent_id = link["parent_id"]
            else:
                for key, value in link["http_headers"]:
                    pb_link.http_headers.http_headers.append(pb.HeaderTuple(key=key, value=value))

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
                span_tags=pb_tags,
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
        links: List[Link],
        http_headers: List[Tuple[str, str]],
        attributes: dict = None,
    ):
        distributed_message = pb.DistributedHTTPHeaders()
        for key, value in http_headers:
            distributed_message.http_headers.append(pb.HeaderTuple(key=key, value=value))

        pb_links = []
        for link in links:
            pb_link = pb.SpanLink(attributes=convert_to_proto(link.get("attributes")))
            if link.get("parent_id") and link.get("http_headers"):
                raise ValueError("Link cannot have both parent_id and http_headers")
            if link.get("parent_id") is not None:
                pb_link.parent_id = link["parent_id"]
            else:
                for key, value in link["http_headers"]:
                    pb_link.http_headers.http_headers.append(pb.HeaderTuple(key=key, value=value))
            pb_links.append(pb_link)

        resp = self._client.OtelStartSpan(
            pb.OtelStartSpanArgs(
                name=name,
                timestamp=timestamp,
                span_kind=span_kind,
                parent_id=parent_id,
                span_links=pb_links,
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

    def span_add_link(
        self, span_id: int, parent_id: int, attributes: dict, http_headers: List[Tuple[str, str]]
    ) -> None:
        pb_link = pb.SpanLink(attributes=convert_to_proto(attributes))
        if parent_id > 0:
            pb_link.parent_id = parent_id
        elif http_headers:
            for key, value in http_headers:
                pb_link.http_headers.http_headers.append(pb.HeaderTuple(key=key, value=value))
        else:
            raise ValueError("Link must have either parent_id or http_headers")

        self._client.SpanAddLink(pb.SpanAddLinkArgs(span_id=span_id, span_link=pb_link,))

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

    def otel_add_event(self, span_id: int, name: str, timestamp: int, attributes):
        self._client.OtelAddEvent(
            pb.OtelAddEventArgs(
                span_id=span_id, name=name, timestamp=timestamp, attributes=convert_to_proto(attributes)
            )
        )

    def otel_record_exception(self, span_id: int, message: str, attributes):
        self._client.OtelRecordException(
            pb.OtelRecordExceptionArgs(span_id=span_id, message=message, attributes=convert_to_proto(attributes))
        )

    def otel_is_recording(self, span_id: int) -> bool:
        return self._client.OtelIsRecording(pb.OtelIsRecordingArgs(span_id=span_id)).is_recording

    def otel_get_span_context(self, span_id: int) -> OtelSpanContext:
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

    def get_tracer_config(self) -> Dict[str, Optional[str]]:
        resp = self._client.GetTraceConfig(pb.GetTraceConfigArgs())
        config_dict = resp.config
        return {
            "dd_service": config_dict.get("dd_service", None),
            "dd_log_level": config_dict.get("dd_log_level", None),
            "dd_trace_sample_rate": config_dict.get("dd_trace_sample_rate", None),
            "dd_trace_enabled": config_dict.get("dd_trace_enabled", None),
            "dd_runtime_metrics_enabled": config_dict.get("dd_runtime_metrics_enabled", None),
            "dd_tags": config_dict.get("dd_tags", None),
            "dd_trace_propagation_style": config_dict.get("dd_trace_propagation_style", None),
            "dd_trace_debug": config_dict.get("dd_trace_debug", None),
            "dd_trace_otel_enabled": config_dict.get("dd_trace_otel_enabled", None),
            "dd_trace_sample_ignore_parent": config_dict.get("dd_trace_sample_ignore_parent", None),
            "dd_env": config_dict.get("dd_env", None),
            "dd_version": config_dict.get("dd_version", None),
        }


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
        tags: Optional[List[Tuple[str, str]]] = None,
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
            tags=tags if tags is not None else [],
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
        links: Optional[List[Link]] = None,
        attributes: dict = None,
        http_headers: Optional[List[Tuple[str, str]]] = None,
    ) -> Generator[_TestOtelSpan, None, None]:
        resp = self._client.otel_trace_start_span(
            name=name,
            timestamp=timestamp,
            span_kind=span_kind,
            parent_id=parent_id,
            links=links if links is not None else [],
            attributes=attributes,
            http_headers=http_headers if http_headers is not None else [],
        )
        span = _TestOtelSpan(self._client, resp["span_id"])
        yield span

        return {
            "span_id": resp["span_id"],
            "trace_id": resp["trace_id"],
        }

    def current_span(self) -> Union[_TestSpan, None]:
        resp = self._client.current_span()
        if resp is None:
            return None
        return _TestSpan(self._client, resp["span_id"], resp["trace_id"])

    def flush(self):
        self._client.trace_flush()

    def otel_flush(self, timeout_sec: int) -> bool:
        return self._client.otel_flush(timeout_sec)

    def otel_current_span(self) -> Union[_TestOtelSpan, None]:
        resp = self._client.otel_current_span()
        if resp is None:
            return None
        return _TestOtelSpan(self._client, resp["span_id"], resp["trace_id"])

    def otel_is_recording(self, span_id: int) -> bool:
        return self._client.otel_is_recording(span_id)

    def inject_headers(self, span_id) -> List[Tuple[str, str]]:
        return self._client.trace_inject_headers(span_id)

    def http_client_request(
        self, url: str, method: str = "GET", headers: List[Tuple[str, str]] = None, body: Optional[bytes] = b"",
    ):
        """Do an HTTP request with the given method and headers."""
        return self._client.http_client_request(method=method, url=url, headers=headers or [], body=body,)

    def finish_span(self, span_id: int) -> None:
        self._client.finish_span(span_id)

    def get_tracer_config(self) -> Dict[str, Optional[str]]:
        return self._client.get_tracer_config()
