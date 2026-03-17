"""RC response builders for test runner side.

This module provides functions to build complete protobuf responses
that can be sent to the proxy as pre-built bytes. These functions
can be imported and used from both the proxy and the test runner.

The agent polls the RC backend via protobuf API at /api/v0.1/configurations.
This module builds valid TUF-signed responses that the agent can validate.
"""

import base64
import json

from .tuf import (
    get_tuf_root_json,
    sign_tuf_document,
    build_targets_content,
    build_snapshot_content,
    build_timestamp_content,
)

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


def build_rc_configurations_protobuf(rc_state: dict | None) -> bytes:
    """Build a LatestConfigsResponse protobuf with proper TUF metadata.

    This builds a complete RC response that the agent can validate using TUF.
    The response includes both config and director repository metadata.

    Args:
        rc_state: RC state dict with 'targets' (base64 signed JSON) and
                  'target_files' (list of {path, raw} dicts). If None,
                  returns empty targets at version 0.

    Returns:
        Protobuf-encoded LatestConfigsResponse bytes

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
        targets_content = build_targets_content(version)
        targets_json = json.dumps(sign_tuf_document(targets_content), separators=(",", ":")).encode()

    # Build snapshot referencing targets
    snapshot_content = build_snapshot_content(version, targets_json)
    snapshot_json = json.dumps(sign_tuf_document(snapshot_content), separators=(",", ":")).encode()

    # Build timestamp referencing snapshot
    timestamp_content = build_timestamp_content(version, snapshot_json)
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


def build_org_data_protobuf(uuid: str = "test-org-uuid") -> bytes:
    """Build an OrgDataResponse protobuf.

    Args:
        uuid: The org UUID to return

    Returns:
        Protobuf-encoded OrgDataResponse bytes

    """
    response = OrgDataResponse(uuid=uuid)
    return response.SerializeToString()


def build_org_status_protobuf(*, enabled: bool = True, authorized: bool = True) -> bytes:
    """Build an OrgStatusResponse protobuf.

    Args:
        enabled: Whether RC is enabled for the org
        authorized: Whether the org is authorized

    Returns:
        Protobuf-encoded OrgStatusResponse bytes

    """
    response = OrgStatusResponse(enabled=enabled, authorized=authorized)
    return response.SerializeToString()
