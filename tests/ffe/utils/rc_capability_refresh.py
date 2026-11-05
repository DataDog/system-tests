"""Wire fixtures and a second RC client for the capability-refresh scenarios."""

import base64
from copy import deepcopy
import hashlib
import json
import uuid

import requests

from utils import interfaces


def configurations() -> tuple[dict, dict]:
    def flag(key: str, value: str) -> dict:
        return {
            "key": key,
            "enabled": True,
            "variationType": "STRING",
            "variations": {"approved": {"key": "approved", "value": value}},
            "allocations": [
                {"key": "default", "rules": [], "splits": [{"variationKey": "approved", "shards": []}], "doLog": False}
            ],
        }

    parent = flag("parent", "parent-value")
    child = flag("child", "dependent-match")
    child["allocations"][0]["rules"] = [
        {
            "conditions": [
                {
                    "flagEvaluation": {"key": "parent"},
                    "operator": "ONE_OF",
                    "value": ["approved"],
                }
            ]
        }
    ]
    base: dict = {
        "createdAt": "2026-01-01T00:00:00Z",
        "format": "SERVER",
        "environment": {"name": "system-tests"},
        "flags": {"parent": parent},
    }
    dependent = deepcopy(base)
    dependent["flags"]["child"] = child
    return base, dependent


def sdk_polls() -> list[dict]:
    return [
        data
        for data in interfaces.library.get_data(path_filters="/v0.7/config")
        if isinstance(data.get("request", {}).get("content"), dict)
        and "FFE_FLAGS" in data["request"]["content"].get("client", {}).get("products", [])
    ]


def acknowledged(client: dict, path: str) -> bool:
    return any(
        state.get("product") == "FFE_FLAGS" and state.get("id") == path.split("/")[3] and state.get("apply_state") == 2
        for state in client.get("state", {}).get("config_states", [])
    )


class CachePreloader:
    """A second capable client populates the real Agent cache using the SDK protocol."""

    def __init__(self, url: str, *, dependent: bool = True) -> None:
        self.url = url
        self.client: dict = {
            "id": f"cache-preloader-{uuid.uuid4()}",
            "is_tracer": True,
            "products": ["FFE_FLAGS"],
            "capabilities": base64.b64encode(((1 << 46) | ((1 << 50) if dependent else 0)).to_bytes(7, "big")).decode(),
            "client_tracer": {
                "runtime_id": str(uuid.uuid4()),
                "language": "java",
                "tracer_version": "1.69.0",
                "service": "cache-preloader",
                "env": "system-tests",
                "app_version": "1",
            },
            "state": {
                "root_version": 1,
                "targets_version": 0,
                "config_states": [],
                "has_error": False,
                "backend_client_state": "",
            },
        }
        self.cache: dict[str, dict] = {}
        self.selected: list[str] = []

    def poll(self) -> list[str]:
        response = requests.post(
            self.url + "/v0.7/config",
            json={
                "client": self.client,
                "cached_target_files": list(self.cache.values()),
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if "targets" in payload:
            targets = json.loads(base64.b64decode(payload["targets"]))["signed"]
            self.client["state"]["targets_version"] = targets["version"]
            self.client["state"]["backend_client_state"] = targets.get("custom", {}).get("opaque_backend_state", "")
            self.selected = payload.get("client_configs", [])
            self.client["state"]["config_states"] = [
                {
                    "id": path.split("/")[3],
                    "product": "FFE_FLAGS",
                    "version": targets["targets"][path]["custom"]["v"],
                    "apply_state": 2,
                }
                for path in self.selected
            ]
            for file in payload.get("target_files", []):
                raw = base64.b64decode(file["raw"])
                self.cache[file["path"]] = {
                    "path": file["path"],
                    "length": len(raw),
                    "hashes": [{"algorithm": "sha256", "hash": hashlib.sha256(raw).hexdigest()}],
                }
        return self.selected
