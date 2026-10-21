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


# The production backend gives the director targets a new, time-based version
# on every response. The mocked backend emulates this by deriving the director
# version from the version of the RC state: director version =
# state version * DIRECTOR_VERSION_MULTIPLIER + revision, where the revision
# counts the responses served for that state. Tracers report the director
# version as their targets_version; integer division by the multiplier maps it
# back to the state version.
DIRECTOR_VERSION_MULTIPLIER = 1000

# Number of director revisions built for each RC state. With the agent polling
# the backend every 5 seconds in system-tests, this covers 5 minutes, after
# which the last revision is served again.
DIRECTOR_REVISIONS = 60


def director_version_to_state_version(director_version: int) -> int:
    """Return the version of the RC state a director targets version was built for."""
    return director_version // DIRECTOR_VERSION_MULTIPLIER


def _build_snapshot_and_timestamp(version: int, targets_json: bytes) -> tuple[bytes, bytes]:
    """Build the signed snapshot and timestamp metadata referencing targets_json."""
    snapshot_content = build_snapshot_content(version, targets_json)
    snapshot_json = json.dumps(sign_tuf_document(snapshot_content), separators=(",", ":")).encode()
    timestamp_content = build_timestamp_content(version, snapshot_json)
    timestamp_json = json.dumps(sign_tuf_document(timestamp_content), separators=(",", ":")).encode()
    return snapshot_json, timestamp_json


def build_rc_configurations_protobufs_with_director_revisions(rc_state: dict) -> list[bytes]:
    """Build the responses that successive agent requests get for rc_state.

    See DIRECTOR_VERSION_MULTIPLIER.
    """
    return [
        build_rc_configurations_protobuf(rc_state, director_revision=revision) for revision in range(DIRECTOR_REVISIONS)
    ]


def build_rc_configurations_protobuf(rc_state: dict | None, director_revision: int | None = None) -> bytes:
    """Build a LatestConfigsResponse protobuf with proper TUF metadata.

    This builds a complete RC response that the agent can validate using TUF.
    The response includes both config and director repository metadata.

    Args:
        rc_state: RC state dict with 'targets' (base64 signed JSON) and
                  'target_files' (list of {path, raw} dicts). If None,
                  returns empty targets at version 0.
        director_revision: If set, the director metadata is re-signed with
                  version state version * DIRECTOR_VERSION_MULTIPLIER +
                  director_revision. Must be smaller than
                  DIRECTOR_VERSION_MULTIPLIER. If None, the director metadata
                  uses the state version.

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

    # Build snapshot and timestamp referencing targets
    snapshot_json, timestamp_json = _build_snapshot_and_timestamp(version, targets_json)

    # Build DirectorMetas using protobuf
    director_version = version
    director_targets_json = targets_json
    director_snapshot_json = snapshot_json
    director_timestamp_json = timestamp_json
    if director_revision is not None:
        if not 0 <= director_revision < DIRECTOR_VERSION_MULTIPLIER:
            raise ValueError(f"director_revision must be in [0, {DIRECTOR_VERSION_MULTIPLIER}): {director_revision}")
        director_version = version * DIRECTOR_VERSION_MULTIPLIER + director_revision
        director_targets_content = json.loads(targets_json)["signed"]
        director_targets_content["version"] = director_version
        director_targets_json = json.dumps(sign_tuf_document(director_targets_content), separators=(",", ":")).encode()
        director_snapshot_json, director_timestamp_json = _build_snapshot_and_timestamp(
            director_version, director_targets_json
        )
    director_metas = DirectorMetas()
    director_metas.roots.append(TopMeta(version=1, raw=root_json))  # type: ignore[attr-defined]
    director_metas.timestamp.CopyFrom(TopMeta(version=director_version, raw=director_timestamp_json))  # type: ignore[attr-defined]
    director_metas.snapshot.CopyFrom(TopMeta(version=director_version, raw=director_snapshot_json))  # type: ignore[attr-defined]
    director_metas.targets.CopyFrom(TopMeta(version=director_version, raw=director_targets_json))  # type: ignore[attr-defined]

    # Build ConfigMetas
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
