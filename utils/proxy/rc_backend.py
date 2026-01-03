"""Remote Config backend mock functionality.

This module provides TUF (The Update Framework) metadata generation and protobuf
encoding for mocking the Datadog Remote Config backend. It allows the proxy to
serve properly signed RC configurations to the agent.

The agent polls the RC backend via protobuf API at /api/v0.1/configurations.
This module builds valid TUF-signed responses that the agent can validate.
"""

import base64
import hashlib
import json

from .tuf import sign_tuf_document, get_tuf_root_json

from ._decoders.protobuf_schemas import (
    LatestConfigsResponse,
    ConfigMetas,
    DirectorMetas,
    TopMeta,
    File,
    OrgDataResponse,
    OrgStatusResponse,
)


def _build_tuf_root() -> bytes:
    """Build a signed TUF root metadata with the test key."""
    return get_tuf_root_json().encode()


def build_rc_protobuf_response(rc_state: dict | None) -> bytes:
    """Build a LatestConfigsResponse protobuf with proper TUF metadata.

    This builds a complete RC response that the agent can validate using TUF.
    The response includes both config and director repository metadata.

    Args:
        rc_state: RC state dict with 'targets' (base64 signed JSON) and
                  'target_files' (list of {path, raw} dicts). If None,
                  returns empty targets at version 0.

    Returns:
        Protobuf-encoded LatestConfigsResponse

    """
    root_json = _build_tuf_root()

    # Build signed targets metadata
    if rc_state and "targets" in rc_state:
        targets_json = base64.b64decode(rc_state["targets"])
        targets_parsed = json.loads(targets_json)
        version = targets_parsed.get("signed", {}).get("version", 1)
    else:
        # Use version 0 for empty state so version 1 updates are accepted
        version = 0
        targets_content = {
            "_type": "targets",
            "custom": {"opaque_backend_state": "eyJmb28iOiAiYmFyIn0="},
            "expires": "3000-01-01T00:00:00Z",
            "spec_version": "1.0",
            "targets": {},
            "version": version,
        }
        targets_json = json.dumps(sign_tuf_document(targets_content), separators=(",", ":")).encode()

    # Build snapshot referencing targets
    targets_hash = hashlib.sha256(targets_json).hexdigest()
    snapshot_content = {
        "_type": "snapshot",
        "expires": "3000-01-01T00:00:00Z",
        "meta": {
            "targets.json": {
                "hashes": {"sha256": targets_hash},
                "length": len(targets_json),
                "version": version,
            }
        },
        "spec_version": "1.0",
        "version": version,
    }
    snapshot_json = json.dumps(sign_tuf_document(snapshot_content), separators=(",", ":")).encode()

    # Build timestamp referencing snapshot
    snapshot_hash = hashlib.sha256(snapshot_json).hexdigest()
    timestamp_content = {
        "_type": "timestamp",
        "expires": "3000-01-01T00:00:00Z",
        "meta": {
            "snapshot.json": {
                "hashes": {"sha256": snapshot_hash},
                "length": len(snapshot_json),
                "version": version,
            }
        },
        "spec_version": "1.0",
        "version": version,
    }
    timestamp_json = json.dumps(sign_tuf_document(timestamp_content), separators=(",", ":")).encode()

    # Build DirectorMetas using protobuf
    director_metas = DirectorMetas()
    director_metas.roots.append(TopMeta(version=1, raw=root_json))  # type: ignore[attr-defined]
    director_metas.timestamp.CopyFrom(TopMeta(version=version, raw=timestamp_json))  # type: ignore[attr-defined]
    director_metas.snapshot.CopyFrom(TopMeta(version=version, raw=snapshot_json))  # type: ignore[attr-defined]
    director_metas.targets.CopyFrom(TopMeta(version=version, raw=targets_json))  # type: ignore[attr-defined]

    # Build ConfigMetas (same structure as director)
    config_metas = ConfigMetas()
    config_metas.roots.append(TopMeta(version=1, raw=root_json))  # type: ignore[attr-defined]
    config_metas.timestamp.CopyFrom(TopMeta(version=version, raw=timestamp_json))  # type: ignore[attr-defined]
    config_metas.snapshot.CopyFrom(TopMeta(version=version, raw=snapshot_json))  # type: ignore[attr-defined]
    config_metas.topTargets.CopyFrom(TopMeta(version=version, raw=targets_json))  # type: ignore[attr-defined]

    # Build target_files
    target_files = []
    if rc_state and "target_files" in rc_state:
        for tf in rc_state["target_files"]:
            target_files.append(File(path=tf["path"], raw=base64.b64decode(tf["raw"])))

    # Build LatestConfigsResponse
    response = LatestConfigsResponse()
    response.config_metas.CopyFrom(config_metas)  # type: ignore[attr-defined]
    response.director_metas.CopyFrom(director_metas)  # type: ignore[attr-defined]
    response.target_files.extend(target_files)  # type: ignore[attr-defined]

    return response.SerializeToString()


def build_org_data_response(uuid: str = "test-org-uuid") -> bytes:
    """Build an OrgDataResponse protobuf.

    Args:
        uuid: The org UUID to return

    Returns:
        Protobuf-encoded OrgDataResponse

    """
    response = OrgDataResponse(uuid=uuid)
    return response.SerializeToString()


def build_org_status_response(*, enabled: bool = True, authorized: bool = True) -> bytes:
    """Build an OrgStatusResponse protobuf.

    Args:
        enabled: Whether RC is enabled for the org
        authorized: Whether the org is authorized

    Returns:
        Protobuf-encoded OrgStatusResponse

    """
    response = OrgStatusResponse(enabled=enabled, authorized=authorized)
    return response.SerializeToString()
