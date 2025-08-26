# pylint: disable=E1101
# pylint: disable=too-many-lines
import contextlib
import time
import urllib.parse
from typing import TypedDict, NotRequired
from types import TracebackType
from collections.abc import Generator, Iterable
from http import HTTPStatus

from docker.models.containers import Container
import pytest
from _pytest.outcomes import Failed
import requests
from opentelemetry.trace import SpanKind, StatusCode
from utils import context

from utils.parametric.spec.otel_trace import OtelSpanContext
from utils._logger import logger


def _fail(message: str):
    """Used to mak a test as failed"""
    logger.error(message)
    raise Failed(message, pytrace=False) from None


class StartSpanResponse(TypedDict):
    span_id: int
    trace_id: int


class SpanResponse(TypedDict):
    span_id: int
    trace_id: int


class Link(TypedDict):
    parent_id: int
    attributes: NotRequired[dict]


class Event(TypedDict):
    time_unix_nano: int
    name: str
    attributes: dict


class APMLibraryClient:
    def __init__(self, url: str, timeout: int, container: Container):
        self._base_url = url
        self._session = requests.Session()
        self.container = container
        self.timeout = timeout

        # wait for server to start
        self._wait(timeout)

    def _wait(self, timeout: float):
        delay = 0.01
        for _ in range(int(timeout / delay)):
            try:
                if self.is_alive():
                    break
            except Exception:
                if self.container.status != "running":
                    self._print_logs()
                    message = f"Container {self.container.name} status is {self.container.status}. Please check logs."
                    _fail(message)
            time.sleep(delay)
        else:
            self._print_logs()
            message = f"Timeout of {timeout} seconds exceeded waiting for HTTP server to start. Please check logs."
            _fail(message)

    def container_restart(self):
        self.container.restart()
        self._wait(self.timeout)

    def is_alive(self) -> bool:
        self.container.reload()
        return (
            self.container.status == "running"
            and self._session.get(self._url("/non-existent-endpoint-to-ping-until-the-server-starts")).status_code
            == HTTPStatus.NOT_FOUND
        )

    def _print_logs(self):
        try:
            logs = self.container.logs().decode("utf-8")
            logger.debug(f"Logs from container {self.container.name}:\n\n{logs}")
        except Exception:
            logger.error(f"Failed to get logs from container {self.container.name}")

    def _url(self, path: str) -> str:
        return urllib.parse.urljoin(self._base_url, path)

    def crash(self) -> None:
        try:
            self._session.get(self._url("/trace/crash"))
        except:
            logger.info("Expected exception when calling /trace/crash")

    def container_exec_run_raw(self, command: str) -> tuple[bool, str]:
        try:
            code, (stdout, _) = self.container.exec_run(command, demux=True)
            if code is None:
                success = False
                message = "Exit code from command in the parametric app container is None"
            elif stdout is None:
                success = False
                message = "Stdout from command in the parametric app container is None"
            else:
                success = True
                message = stdout
        except BaseException:
            return (
                False,
                "Encountered an issue running command in the parametric app container",
            )

        return success, message

    def container_exec_run(self, command: str) -> tuple[bool, str]:
        try:
            code, (stdout, stderr) = self.container.exec_run(command, demux=True)
            if code is None:
                success = False
                message = "Exit code from command in the parametric app container is None"
            elif stderr is not None or code != 0:
                success = False
                message = f"Error code {code}: {stderr.decode()}"
            else:
                success = True
                message = stdout.decode() if stdout is not None else ""
        except BaseException:
            return (
                False,
                "Encountered an issue running command in the parametric app container",
            )

        return success, message

    def trace_start_span(
        self,
        name: str,
        service: str | None = None,
        resource: str | None = None,
        parent_id: str | int | None = None,
        typestr: str | None = None,
        tags: list[tuple[str, str]] | None = None,
    ):
        if context.library == "cpp":
            # TODO: Update the cpp parametric app to accept null values for unset parameters
            service = service or ""
            resource = resource or ""
            parent_id = parent_id or 0
            typestr = typestr or ""

        resp = self._session.post(
            self._url("/trace/span/start"),
            json={
                "name": name,
                "service": service,
                "resource": resource,
                "parent_id": parent_id,
                "type": typestr,
                "span_tags": tags if tags is not None else [],
            },
        )

        if resp.status_code != HTTPStatus.OK:
            raise pytest.fail(f"Failed to start span: {resp.text}", pytrace=False)

        resp_json = resp.json()
        return StartSpanResponse(span_id=resp_json["span_id"], trace_id=resp_json["trace_id"])

    def current_span(self) -> SpanResponse | None:
        resp_json = self._session.get(self._url("/trace/span/current")).json()
        if not resp_json:
            return None
        return SpanResponse(span_id=resp_json["span_id"], trace_id=resp_json["trace_id"])

    def finish_span(self, span_id: int) -> None:
        self._session.post(self._url("/trace/span/finish"), json={"span_id": span_id})

    def span_set_resource(self, span_id: int, resource: str) -> None:
        self._session.post(
            self._url("/trace/span/set_resource"),
            json={"span_id": span_id, "resource": resource},
        )

    def span_set_meta(self, span_id: int, key: str, value: str | bool | list[str | list[str]] | None) -> None:
        self._session.post(
            self._url("/trace/span/set_meta"),
            json={"span_id": span_id, "key": key, "value": value},
        )

    def span_set_baggage(self, span_id: int, key: str, value: str) -> None:
        self._session.post(
            self._url("/trace/span/set_baggage"),
            json={"span_id": span_id, "key": key, "value": value},
        )

    def span_remove_baggage(self, span_id: int, key: str) -> None:
        self._session.post(
            self._url("/trace/span/remove_baggage"),
            json={"span_id": span_id, "key": key},
        )

    def span_remove_all_baggage(self, span_id: int) -> None:
        self._session.post(self._url("/trace/span/remove_all_baggage"), json={"span_id": span_id})

    def span_set_metric(self, span_id: int, key: str, value: float | list[int]) -> None:
        self._session.post(self._url("/trace/span/set_metric"), json={"span_id": span_id, "key": key, "value": value})

    def span_set_error(self, span_id: int, typestr: str, message: str, stack: str) -> None:
        self._session.post(
            self._url("/trace/span/error"),
            json={
                "span_id": span_id,
                "type": typestr,
                "message": message,
                "stack": stack,
            },
        )

    def span_add_link(self, span_id: int, parent_id: int, attributes: dict | None = None):
        self._session.post(
            self._url("/trace/span/add_link"),
            json={
                "span_id": span_id,
                "parent_id": parent_id,
                "attributes": attributes or {},
            },
        )

    def span_add_event(self, span_id: int, name: str, time_unix_nano: int, attributes: dict | None = None):
        self._session.post(
            self._url("/trace/span/add_event"),
            json={
                "span_id": span_id,
                "name": name,
                "timestamp": time_unix_nano,
                "attributes": attributes or {},
            },
        )

    def span_get_baggage(self, span_id: int, key: str) -> str:
        resp = self._session.get(self._url("/trace/span/get_baggage"), json={"span_id": span_id, "key": key})
        data = resp.json()
        return data["baggage"]

    def span_get_all_baggage(self, span_id: int) -> dict:
        resp = self._session.get(self._url("/trace/span/get_all_baggage"), json={"span_id": span_id})
        data = resp.json()
        return data["baggage"]

    def trace_inject_headers(self, span_id: int):
        resp = self._session.post(self._url("/trace/span/inject_headers"), json={"span_id": span_id})
        # TODO: translate json into list within list
        # so server.xx do not have to
        return resp.json()["http_headers"]

    def trace_extract_headers(self, http_headers: Iterable[tuple[str, str]]):
        resp = self._session.post(
            self._url("/trace/span/extract_headers"),
            json={"http_headers": http_headers},
        )
        return resp.json()["span_id"]

    def trace_flush(self) -> bool:
        r = self._session.post(self._url("/trace/span/flush"), json={})

        if not HTTPStatus(r.status_code).is_success:
            return False

        r = self._session.post(self._url("/trace/stats/flush"), json={})

        return HTTPStatus(r.status_code).is_success

    def otel_trace_start_span(
        self,
        name: str,
        timestamp: int | None,
        span_kind: SpanKind | None,
        parent_id: int | None,
        links: list[Link] | None,
        events: list[Event] | None,
        attributes: dict | None,
    ) -> StartSpanResponse:
        resp = self._session.post(
            self._url("/trace/otel/start_span"),
            json={
                "name": name,
                "timestamp": timestamp,
                "parent_id": parent_id,
                "span_kind": span_kind.value if span_kind is not None else None,
                "links": links or [],
                "events": events or [],
                "attributes": attributes or {},
            },
        ).json()
        # TODO: Some http endpoints return span_id and trace_id as strings (ex: dotnet), some as uint64 (ex: go)
        # and others with bignum trace_ids and uint64 span_ids (ex: python). We should standardize this.
        return StartSpanResponse(span_id=resp["span_id"], trace_id=resp["trace_id"])

    def otel_end_span(self, span_id: int, timestamp: int | None) -> None:
        self._session.post(
            self._url("/trace/otel/end_span"),
            json={"id": span_id, "timestamp": timestamp},
        )

    def otel_set_attributes(self, span_id: int, attributes: dict) -> None:
        self._session.post(
            self._url("/trace/otel/set_attributes"),
            json={"span_id": span_id, "attributes": attributes},
        )

    def otel_set_name(self, span_id: int, name: str) -> None:
        self._session.post(self._url("/trace/otel/set_name"), json={"span_id": span_id, "name": name})

    def otel_set_status(self, span_id: int, code: StatusCode, description: str) -> None:
        self._session.post(
            self._url("/trace/otel/set_status"),
            json={"span_id": span_id, "code": code.name, "description": description},
        )

    def otel_add_event(self, span_id: int, name: str, timestamp: int | None, attributes: dict | None) -> None:
        self._session.post(
            self._url("/trace/otel/add_event"),
            json={
                "span_id": span_id,
                "name": name,
                "timestamp": timestamp,
                "attributes": attributes,
            },
        )

    def otel_record_exception(self, span_id: int, message: str, attributes: dict | None) -> None:
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

    def otel_set_baggage(self, span_id: int, key: str, value: str) -> None:
        resp = self._session.post(
            self._url("/trace/otel/otel_set_baggage"),
            json={"span_id": span_id, "key": key, "value": value},
        )
        data = resp.json()
        return data["value"]

    def config(self) -> dict[str, str | None]:
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
            "dd_trace_agent_url": config_dict.get("dd_trace_agent_url", None),
            "dd_trace_rate_limit": config_dict.get("dd_trace_rate_limit", None),
            "dd_dogstatsd_host": config_dict.get("dd_dogstatsd_host", None),
            "dd_dogstatsd_port": config_dict.get("dd_dogstatsd_port", None),
            "dd_logs_injection": config_dict.get("dd_logs_injection", None),
            "dd_profiling_enabled": config_dict.get("dd_profiling_enabled", None),
            "dd_data_streams_enabled": config_dict.get("dd_data_streams_enabled", None),
        }

    def otel_current_span(self) -> SpanResponse | None:
        resp = self._session.get(self._url("/trace/otel/current_span"), json={})
        if not resp:
            return None

        resp_json = resp.json()
        return SpanResponse(span_id=resp_json["span_id"], trace_id=resp_json["trace_id"])

    def otel_get_meter(self, name: str, version: str | None = None, schema_url: str | None = None, attributes: dict | None = None) -> None:
        self._session.post(
            self._url("/metrics/otel/get_meter"),
            json={"name": name, "version": version, "schema_url": schema_url, "attributes": attributes},
        )

    def otel_create_counter(self, meter_name: str, name: str, unit: str, description: str) -> None:
        self._session.post(
            self._url("/metrics/otel/create_counter"),
            json={"meter_name": meter_name, "name": name, "unit": unit, "description": description},
        )

    def otel_counter_add(self, meter_name: str, name: str, unit: str, description: str, value: float, attributes: dict | None) -> None:
        self._session.post(
            self._url("/metrics/otel/counter_add"),
            json={"meter_name": meter_name, "name": name, "unit": unit, "description": description, "value": value, "attributes": attributes},
        )

    def otel_create_updowncounter(self, meter_name: str, name: str, unit: str, description: str) -> None:
        self._session.post(
            self._url("/metrics/otel/create_updowncounter"),
            json={"meter_name": meter_name, "name": name, "unit": unit, "description": description},
        )

    def otel_updowncounter_add(self, meter_name: str, name: str, unit: str, description: str, value: float, attributes: dict | None) -> None:
        self._session.post(
            self._url("/metrics/otel/updowncounter_add"),
            json={"meter_name": meter_name, "name": name, "unit": unit, "description": description, "value": value, "attributes": attributes},
        )

    def otel_create_gauge(self, meter_name: str, name: str, unit: str, description: str) -> None:
        self._session.post(
            self._url("/metrics/otel/create_gauge"),
            json={"meter_name": meter_name, "name": name, "unit": unit, "description": description},
        )

    def otel_gauge_record(self, meter_name: str, name: str, unit: str, description: str, value: float, attributes: dict | None) -> None:
        self._session.post(
            self._url("/metrics/otel/gauge_record"),
            json={"meter_name": meter_name, "name": name, "unit": unit, "description": description, "value": value, "attributes": attributes},
        )

    def otel_create_histogram(self, meter_name: str, name: str, unit: str, description: str) -> None:
        self._session.post(
            self._url("/metrics/otel/create_histogram"),
            json={"meter_name": meter_name, "name": name, "unit": unit, "description": description},
        )

    def otel_histogram_record(self, meter_name: str, name: str, unit: str, description: str, value: float, attributes: dict | None) -> None:
        self._session.post(
            self._url("/metrics/otel/histogram_record"),
            json={"meter_name": meter_name, "name": name, "unit": unit, "description": description, "value": value, "attributes": attributes},
        )

    def otel_create_asynchronous_counter(self, meter_name: str, name: str, unit: str, description: str, value: float, attributes: dict | None) -> None:
        self._session.post(
            self._url("/metrics/otel/create_asynchronous_counter"),
            json={"meter_name": meter_name, "name": name, "unit": unit, "description": description, "value": value, "attributes": attributes},
        )

    def otel_create_asynchronous_updowncounter(self, meter_name: str, name: str, unit: str, description: str, value: float, attributes: dict | None) -> None:
        self._session.post(
            self._url("/metrics/otel/create_asynchronous_updowncounter"),
            json={"meter_name": meter_name, "name": name, "unit": unit, "description": description, "value": value, "attributes": attributes},
        )


class _TestSpan:
    def __init__(self, client: APMLibraryClient, span_id: int, trace_id: int):
        self._client = client
        self.span_id = span_id
        self.trace_id = trace_id

    def set_resource(self, resource: str):
        self._client.span_set_resource(self.span_id, resource)

    def set_meta(self, key: str, val: str | bool | list[str | list[str]] | None):
        self._client.span_set_meta(self.span_id, key, val)

    def set_metric(self, key: str, val: float | list[int]):
        self._client.span_set_metric(self.span_id, key, val)

    def set_baggage(self, key: str, val: str):
        self._client.span_set_baggage(self.span_id, key, val)

    def get_baggage(self, key: str):
        return self._client.span_get_baggage(self.span_id, key)

    def get_all_baggage(self):
        return self._client.span_get_all_baggage(self.span_id)

    def remove_baggage(self, key: str):
        self._client.span_remove_baggage(self.span_id, key)

    def remove_all_baggage(self):
        self._client.span_remove_all_baggage(self.span_id)

    def set_error(self, typestr: str = "", message: str = "", stack: str = ""):
        self._client.span_set_error(self.span_id, typestr, message, stack)

    def add_link(self, parent_id: int, attributes: dict | None = None):
        self._client.span_add_link(self.span_id, parent_id, attributes)

    def add_event(self, name: str, time_unix_nano: int, attributes: dict | None = None):
        self._client.span_add_event(self.span_id, name, time_unix_nano, attributes)

    def finish(self):
        self._client.finish_span(self.span_id)


class _TestOtelSpan:
    def __init__(self, client: APMLibraryClient, span_id: int, trace_id: int):
        self._client = client
        self.span_id = span_id
        self.trace_id = trace_id

    # API methods

    def set_attributes(self, attributes: dict):
        self._client.otel_set_attributes(self.span_id, attributes)

    def set_attribute(self, key: str, value: str | float | list[str | float | list[str]] | None):
        self._client.otel_set_attributes(self.span_id, {key: value})

    def set_name(self, name: str):
        self._client.otel_set_name(self.span_id, name)

    def set_status(self, code: StatusCode, description: str):
        self._client.otel_set_status(self.span_id, code, description)

    def add_event(self, name: str, timestamp: int | None = None, attributes: dict | None = None):
        self._client.otel_add_event(self.span_id, name, timestamp, attributes)

    def record_exception(self, message: str, attributes: dict | None = None):
        self._client.otel_record_exception(self.span_id, message, attributes)

    def end_span(self, timestamp: int | None = None):
        self._client.otel_end_span(self.span_id, timestamp)

    def is_recording(self) -> bool:
        return self._client.otel_is_recording(self.span_id)

    def span_context(self) -> OtelSpanContext:
        return self._client.otel_get_span_context(self.span_id)

    def set_baggage(self, key: str, value: str):
        self._client.otel_set_baggage(self.span_id, key, value)


class APMLibrary:
    def __init__(self, client: APMLibraryClient, lang: str):
        self._client = client
        self.lang = lang
        self.flush_traces = True

    def __enter__(self) -> "APMLibrary":
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> bool | None:
        # Only attempt a flush if there was no exception raised.
        if exc_type is None and self.flush_traces:
            self.dd_flush()
            if self.lang != "cpp":
                # C++ does not have an otel/flush endpoint
                self.otel_flush(1)

        return None

    def disable_traces_flush(self):
        self.flush_traces = False

    def crash(self) -> None:
        self._client.crash()

    def container_exec_run(self, command: str) -> tuple[bool, str]:
        return self._client.container_exec_run(command)

    def container_restart(self):
        self._client.container_restart()

    def container_exec_run_raw(self, command: str) -> tuple[bool, str]:
        return self._client.container_exec_run_raw(command)

    @contextlib.contextmanager
    def dd_start_span(
        self,
        name: str,
        service: str | None = None,
        resource: str | None = None,
        parent_id: str | int | None = None,
        typestr: str | None = None,
        tags: list[tuple[str, str]] | None = None,
    ) -> Generator[_TestSpan, None, None]:
        resp = self._client.trace_start_span(
            name=name,
            service=service,
            resource=resource,
            parent_id=parent_id,
            typestr=typestr,
            tags=tags,
        )
        span = _TestSpan(self._client, resp["span_id"], resp["trace_id"])
        yield span
        span.finish()

    def dd_extract_headers_and_make_child_span(self, name: str, http_headers: Iterable[tuple[str, str]]):
        parent_id = self.dd_extract_headers(http_headers=http_headers)
        return self.dd_start_span(name=name, parent_id=parent_id)

    def dd_make_child_span_and_get_headers(self, headers: Iterable[tuple[str, str]]) -> dict[str, str]:
        with self.dd_extract_headers_and_make_child_span("name", headers) as span:
            headers = self.dd_inject_headers(span.span_id)
            return {k.lower(): v for k, v in headers}

    @contextlib.contextmanager
    def otel_start_span(
        self,
        name: str,
        timestamp: int | None = None,
        span_kind: SpanKind | None = None,
        parent_id: int | None = None,
        links: list[Link] | None = None,
        events: list[Event] | None = None,
        attributes: dict | None = None,
        *,
        end_on_exit: bool = True,
    ) -> Generator[_TestOtelSpan, None, None]:
        resp = self._client.otel_trace_start_span(
            name=name,
            timestamp=timestamp,
            span_kind=span_kind,
            parent_id=parent_id,
            links=links,
            events=events if events is not None else [],
            attributes=attributes,
        )
        span = _TestOtelSpan(self._client, resp["span_id"], resp["trace_id"])
        yield span
        if end_on_exit:
            span.end_span()

    def dd_flush(self) -> bool:
        return self._client.trace_flush()

    def otel_flush(self, timeout_sec: int) -> bool:
        return self._client.otel_flush(timeout_sec)

    def otel_is_recording(self, span_id: int) -> bool:
        return self._client.otel_is_recording(span_id)

    def dd_inject_headers(self, span_id: int) -> list[tuple[str, str]]:
        return self._client.trace_inject_headers(span_id)

    def dd_extract_headers(self, http_headers: Iterable[tuple[str, str]]) -> int:
        return self._client.trace_extract_headers(http_headers)

    def otel_set_baggage(self, span_id: int, key: str, value: str):
        return self._client.otel_set_baggage(span_id, key, value)

    def config(self) -> dict[str, str | None]:
        return self._client.config()

    def dd_current_span(self) -> _TestSpan | None:
        resp = self._client.current_span()
        if resp is None:
            return None
        return _TestSpan(self._client, resp["span_id"], resp["trace_id"])

    def otel_current_span(self) -> _TestOtelSpan | None:
        resp = self._client.otel_current_span()
        if resp is None:
            return None
        return _TestOtelSpan(self._client, resp["span_id"], resp["trace_id"])

    def otel_get_meter(self, name: str, version: str | None = None, schema_url: str | None = None, attributes: dict | None = None) -> None:
        self._client.otel_get_meter(name, version, schema_url, attributes)

    def otel_create_counter(self, meter_name: str, name: str, unit: str, description: str) -> None:
        self._client.otel_create_counter(meter_name, name, unit, description)

    def otel_counter_add(self, meter_name: str, name: str, unit: str, description: str, value: float, attributes: dict | None = None) -> None:
        self._client.otel_counter_add(meter_name, name, unit, description, value, attributes)

    def otel_create_updowncounter(self, meter_name: str, name: str, unit: str, description: str) -> None:
        self._client.otel_create_updowncounter(meter_name, name, unit, description)

    def otel_updowncounter_add(self, meter_name: str, name: str, unit: str, description: str, value: float, attributes: dict | None = None) -> None:
        self._client.otel_updowncounter_add(meter_name, name, unit, description, value, attributes)

    def otel_create_gauge(self, meter_name: str, name: str, unit: str, description: str) -> None:
        self._client.otel_create_gauge(meter_name, name, unit, description)

    def otel_gauge_record(self, meter_name: str, name: str, unit: str, description: str, value: float, attributes: dict | None = None) -> None:
        self._client.otel_gauge_record(meter_name, name, unit, description, value, attributes)

    def otel_create_histogram(self, meter_name: str, name: str, unit: str, description: str) -> None:
        self._client.otel_create_histogram(meter_name, name, unit, description)

    def otel_histogram_record(self, meter_name: str, name: str, unit: str, description: str, value: float, attributes: dict | None = None) -> None:
        self._client.otel_histogram_record(meter_name, name, unit, description, value, attributes)

    def otel_create_asynchronous_counter(self, meter_name: str, name: str, unit: str, description: str, value: float, attributes: dict | None) -> None:
        self._client.otel_create_asynchronous_counter(meter_name, name, unit, description, value, attributes)

    def otel_create_asynchronous_updowncounter(self, meter_name: str, name: str, unit: str, description: str, value: float, attributes: dict | None) -> None:
        self._client.otel_create_asynchronous_updowncounter(meter_name, name, unit, description, value, attributes)

    def is_alive(self) -> bool:
        try:
            return self._client.is_alive()
        except Exception:
            return False
