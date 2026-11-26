"""Scripted precompute-assignments responses, not an implementation of origin evaluation/rollouts."""

import hashlib
from typing import Any

PRECOMPUTED_CONFIG_PATH = "/precompute-assignments"


def precomputed_response(mode: str) -> dict[str, Any]:
    # JSON:API envelope and assignment fields follow the public browser precomputed-v1
    # fixture shape; flag keys, values, serialId, and features are local test data.
    # Encoding metadata follows flag-key-sha256-v1; selection/policy outcomes are scripted.
    assignment = {
        "allocationKey": "allocation",
        "variationKey": "on",
        "variationType": "boolean",
        "variationValue": True,
        "reason": "TARGETING_MATCH",
        "doLog": True,
        "serialId": 7,
        "features": [{"key": "checkout", "value": False, "destinations": ["HOOK", "EXPOSURE"]}],
    }
    flags = {
        "test-flag": assignment,
        "false-flag": {**assignment, "variationKey": "off", "variationValue": False},
        "nullable": {**assignment, "variationType": "object", "variationValue": None},
    }
    attributes: dict[str, Any] = {
        "createdAt": "2026-11-06T12:00:00Z",
        "environment": {"name": "test"},
        "format": "PRECOMPUTED",
        "obfuscated": False,
        "observeFullEvaluationData": False,
        "flags": flags,
    }
    if mode in ("encoded", "unknown_encoding"):
        salt = "000102030405060708090a0b0c0d0e0f"
        attributes.update({"obfuscated": True, "obfuscation": {"scheme": "flag-key-sha256-v1", "salt": salt}})
        attributes["flags"] = {
            hashlib.sha256(
                b"datadog.feature-flags.flag-key.v1\0" + bytes.fromhex(salt) + key.encode()
            ).hexdigest(): value
            for key, value in flags.items()
        }
        if mode == "unknown_encoding":
            attributes["obfuscation"]["scheme"] = "unsupported-encoding"
    elif mode == "selected_empty":
        attributes["flags"] = {}
    elif mode in ("opt_out_immediate", "opt_out_future", "opt_out_mismatch"):
        attributes["evaluation_options"] = {
            "experimentation_opt_out": True,
            "experimentation_opt_out_mode": "future_experiments_only"
            if mode in ("opt_out_future", "opt_out_mismatch")
            else "immediate",
            "dd_experimentation_opt_out_at": "2026-11-06T12:00:00Z"
            if mode != "opt_out_mismatch"
            else "2026-11-07T12:00:00Z",
        }
    return {"data": {"id": "subject", "type": "precomputed-assignments", "attributes": attributes}}
