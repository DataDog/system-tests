"""Capability-aware RC director fixture. Configuration publication is immutable.

The real backend selects by capabilities, then targets client IDs in director metadata.
This models that contract; it does not test the production backend's implementation.
"""

from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
import threading

from utils.proxy._decoders.protobuf_schemas import LatestConfigsResponse
from utils.proxy.rc_response_builder import build_rc_configurations_protobuf
from utils.proxy.tuf import build_signed_targets

BASE_PATH = "datadog/2/FFE_FLAGS/capability-base/config"
DEPENDENT_PATH = "datadog/2/FFE_FLAGS/capability-dependent/config"


def capability_mask(value: str | list[int]) -> int:
    raw = base64.b64decode(value) if isinstance(value, str) else bytes(item & 255 for item in value)
    return int.from_bytes(raw, "big")


class CapabilityRoutingFixture:
    """Publish once, and renew signed director metadata on ordinary Agent polls.

    The configuration repository, file hashes and file versions never change.
    Director versions advance even when the union of selected files is unchanged,
    as happens when a second client already populated the Agent's cache.
    """

    def __init__(self, base: dict, dependent: dict) -> None:
        self._lock = threading.Lock()
        self._version = 0
        self._history: list[dict] = []
        self._files = {
            path: json.dumps(payload, separators=(",", ":")).encode()
            for path, payload in ((BASE_PATH, base), (DEPENDENT_PATH, dependent))
        }
        self._metadata: dict[str, dict] = {
            path: {"length": len(raw), "hashes": {"sha256": hashlib.sha256(raw).hexdigest()}, "custom": {"v": 1}}
            for path, raw in self._files.items()
        }
        published = LatestConfigsResponse.FromString(self._response(1, self._metadata))
        self._config_metas = published.config_metas  # type: ignore[attr-defined]

    def _response(self, version: int, targets: dict) -> bytes:
        return build_rc_configurations_protobuf(
            {
                "targets": base64.b64encode(json.dumps(build_signed_targets(version, targets)).encode()).decode(),
                "target_files": [
                    {"path": path, "raw": base64.b64encode(self._files[path]).decode()} for path in targets
                ],
            }
        )

    def respond(self, active_clients: list[dict]) -> bytes:
        with self._lock:
            targets: dict = {}
            selected: dict[str, str] = {}
            for client in active_clients:
                bits = capability_mask(client.get("capabilities", ""))
                if "FFE_FLAGS" not in client.get("products", []) or not bits & (1 << 46):
                    continue
                path = DEPENDENT_PATH if bits & (1 << 50) else BASE_PATH
                selected[client["id"]] = path
                if path not in targets:
                    targets[path] = deepcopy(self._metadata[path])
                    targets[path]["custom"]["c"] = []
                    targets[path]["custom"]["tracer-predicates"] = {"tracer_predicates_v1": []}
                targets[path]["custom"]["c"].append(client["id"])
                targets[path]["custom"]["tracer-predicates"]["tracer_predicates_v1"].append({"clientID": client["id"]})
            self._version += 1
            response = LatestConfigsResponse.FromString(self._response(self._version, targets))
            response.config_metas.CopyFrom(self._config_metas)  # type: ignore[attr-defined]
            self._history.append({"version": self._version, "selected": selected})
            self._history = self._history[-100:]
            return response.SerializeToString()

    def status(self) -> dict:
        with self._lock:
            return {
                "publications": 1,
                "config_version": 1,
                "hashes": {path: meta["hashes"]["sha256"] for path, meta in self._metadata.items()},
                "history": deepcopy(self._history),
            }
