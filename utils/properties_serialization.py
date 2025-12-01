import inspect
import json
from typing import Any

import pytest
from requests.structures import CaseInsensitiveDict

from utils._weblog import HttpResponse, GrpcResponse, _Weblog
from utils._remote_config import RemoteConfigStateResults
from utils.interfaces._core import InterfaceValidator
from utils._logger import logger


class _PropertiesEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:  # noqa: ANN401
        if isinstance(o, CaseInsensitiveDict):
            return dict(o.items())

        if isinstance(o, (HttpResponse, GrpcResponse, RemoteConfigStateResults)):
            serialized = o.to_json()
            assert "__class__" not in serialized
            return serialized | {"__class__": o.__class__.__name__}

        if isinstance(o, set):
            return {"__class__": "set", "values": list(o)}

        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, o)


class _PropertiesDecoder(json.JSONDecoder):
    def __init__(self):
        json.JSONDecoder.__init__(self, object_hook=_PropertiesDecoder.from_dict)

    @staticmethod
    def from_dict(d: dict) -> object:
        if klass := d.get("__class__"):
            if klass == "set":
                return set(d["values"])

            if klass == "GrpcResponse":
                return GrpcResponse.from_json(d)

            if klass == "HttpResponse":
                return HttpResponse.from_json(d)

            if klass == "RemoteConfigStateResults":
                return RemoteConfigStateResults.from_json(d)

        return d


class SetupProperties:
    """Store all properties initialized by setup function, and dump =them into a file
    In replay mode, it will restore then to the good instance
    """

    def __init__(self):
        self._store = {}

    def store_properties(self, item: pytest.Item) -> None:
        if properties := self._get_properties(item.instance):
            self._store[item.nodeid] = properties

    def restore_properties(self, item: pytest.Item) -> None:
        if properties := self._store.get(item.nodeid):
            for name, value in properties.items():
                logger.debug(f"Restoring {name} for {item.nodeid}")
                setattr(item.instance, name, value)

    @staticmethod
    def _get_properties(instance: object) -> dict:
        properties = {
            name: getattr(instance, name)
            for name in dir(instance)
            if not name.startswith("_") and name not in ("pytestmark",)
        }

        # removes methods, functions and computed properties
        # also removes properties that already exists on the class
        return {
            name: value
            for name, value in properties.items()
            if not inspect.ismethod(value)
            and not inspect.isfunction(value)
            and not isinstance(getattr(type(instance), name, None), property)
            and not isinstance(value, (_Weblog, InterfaceValidator))  # values that do not carry any tested data
        }

    def dump(self, host_log_folder: str) -> None:
        with open(f"{host_log_folder}/setup_properties.json", "w", encoding="utf-8") as f:
            json.dump(self._store, f, indent=2, cls=_PropertiesEncoder)

    def load(self, host_log_folder: str) -> None:
        filename = f"{host_log_folder}/setup_properties.json"
        try:
            with open(filename, encoding="utf-8") as f:
                self._store = json.load(f, cls=_PropertiesDecoder)
        except FileNotFoundError:
            pytest.exit(f"{filename} does not exists. Did you run the tests without any INTERNALERROR output?")

    def log_requests(self, item: pytest.Item) -> None:
        if properties := self._store.get(item.nodeid):
            self._log_requests(properties)

    def _log_requests(self, o: object) -> None:
        if isinstance(o, HttpResponse):
            logger.info(f"weblog {o.request.method} {o.request.url} -> {o.status_code}")
        elif isinstance(o, GrpcResponse):
            logger.info("weblog GRPC request")
        elif isinstance(o, dict):
            self._log_requests(list(o.values()))
        elif isinstance(o, list):
            for value in o:
                self._log_requests(value)


if __name__ == "__main__":
    SetupProperties().load("logs")
