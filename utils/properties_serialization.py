import inspect
import json

import pytest
from requests.structures import CaseInsensitiveDict

from utils._weblog import HttpResponse, GrpcResponse
from utils.tools import logger


class _PropertiesEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, CaseInsensitiveDict):
            return dict(o.items())

        if isinstance(o, (HttpResponse, GrpcResponse)):
            return o.serialize()

        if isinstance(o, set):
            return {"__class__": "set", "values": list(o)}

        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, o)


class _PropertiesDecoder(json.JSONDecoder):
    def __init__(self):
        json.JSONDecoder.__init__(self, object_hook=_PropertiesDecoder.from_dict)

    @staticmethod
    def from_dict(d):
        if klass := d.get("__class__"):
            if klass == "set":
                return set(d["values"])

            if klass == "GrpcResponse":
                return GrpcResponse(d)

            if klass == "HttpResponse":
                return HttpResponse(d)

        return d


class SetupProperties:
    """ 
        This class will store all properties initialized by setup function, and dump =them into a file
        In replay mode, it will restore then to the good instance 
    """

    def __init__(self):
        self._store = {}

    def add_test_item(self, item: pytest.Item):
        if properties := self._serialize(item.instance):
            self._store[item.nodeid] = properties

    def restore_test_item(self, item: pytest.Item):
        if properties := self._store.get(item.nodeid):
            for name, value in properties.items():
                logger.debug(f"Restoring {name} for {item.nodeid}")
                setattr(item.instance, name, value)

    @staticmethod
    def _serialize(instance) -> dict:

        properties = {
            name: getattr(instance, name)
            for name in dir(instance)
            if not name.startswith("_") and name not in ("pytestmark",)
        }

        # removes methods, functions and computed properties
        return {
            name: value
            for name, value in properties.items()
            if not inspect.ismethod(value)
            and not inspect.isfunction(value)
            and not isinstance(getattr(type(instance), name, None), property)
        }

    def dump(self, host_log_folder: str):
        with open(f"{host_log_folder}/setup_properties.json", "w", encoding="utf-8") as f:
            json.dump(self._store, f, indent=2, cls=_PropertiesEncoder)

    def load(self, host_log_folder: str):
        with open(f"{host_log_folder}/setup_properties.json", "r", encoding="utf-8") as f:
            self._store = json.load(f, cls=_PropertiesDecoder)


if __name__ == "__main__":
    SetupProperties().load("logs")
