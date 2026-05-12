# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""TUF (The Update Framework) signing utilities for Remote Configuration testing.

This module provides a deterministic ed25519 keypair and functions for signing
TUF metadata used in system tests. The key is intentionally reproducible to
ensure consistent test behavior.
"""

import hashlib
import json

from nacl.signing import SigningKey

# =============================================================================
# Test TUF Signing Key
# =============================================================================
#
# This is a deterministic ed25519 keypair used for signing TUF metadata in tests.
# Using a zero seed makes the key reproducible across test runs.
#
# Key derivation:
#   seed = 32 zero bytes (0x00 * 32)
#   signing_key = ed25519.SigningKey(seed)
#   public_key = signing_key.verify_key
#   keyid = sha256(public_key_bytes).hex()
#
# Resulting values:
#   public_key_hex = "3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29"
#   keyid = "139e3940e64b5491722088d9a0d741628fc826e09475d341a780acde3c4b8070"
#
TEST_TUF_SIGNING_KEY_SEED = bytes.fromhex("0" * 64)  # 32 zero bytes as seed
TEST_TUF_SIGNING_KEY = SigningKey(TEST_TUF_SIGNING_KEY_SEED)
TEST_TUF_PUBLIC_KEY = TEST_TUF_SIGNING_KEY.verify_key
TEST_TUF_PUBLIC_KEY_HEX = TEST_TUF_PUBLIC_KEY.encode().hex()
TEST_TUF_KEYID = hashlib.sha256(TEST_TUF_PUBLIC_KEY.encode()).hexdigest()


def sign_tuf_document(signed_content: dict) -> dict:
    """Sign a TUF document (root or targets) using the test ed25519 key.

    TUF requires canonical JSON (sorted keys, no whitespace) for signature verification.

    Args:
        signed_content: The "signed" portion of the TUF document

    Returns:
        Complete TUF document with {signatures: [...], signed: {...}}

    """
    canonical_json = json.dumps(signed_content, separators=(",", ":"), sort_keys=True).encode()
    signature = TEST_TUF_SIGNING_KEY.sign(canonical_json).signature.hex()

    return {
        "signatures": [{"keyid": TEST_TUF_KEYID, "sig": signature}],
        "signed": signed_content,
    }


def _build_tuf_root() -> dict:
    """Build the TUF root metadata structure.

    The root document defines the trusted keys and roles for TUF.
    All roles (root, snapshot, targets, timestamp) use the same test key.
    """
    return {
        "_type": "root",
        "consistent_snapshot": True,
        "expires": "3000-01-01T00:00:00Z",  # Far future expiry for testing
        "keys": {
            TEST_TUF_KEYID: {
                "keyid_hash_algorithms": ["sha256"],
                "keytype": "ed25519",
                "keyval": {"public": TEST_TUF_PUBLIC_KEY_HEX},
                "scheme": "ed25519",
            }
        },
        "roles": {
            "root": {"keyids": [TEST_TUF_KEYID], "threshold": 1},
            "snapshot": {"keyids": [TEST_TUF_KEYID], "threshold": 1},
            "targets": {"keyids": [TEST_TUF_KEYID], "threshold": 1},
            "timestamp": {"keyids": [TEST_TUF_KEYID], "threshold": 1},
        },
        "spec_version": "1.0",
        "version": 1,
    }


def get_tuf_root_json() -> str:
    """Get the signed TUF root document as a JSON string.

    This is used to configure the Datadog agent's remote configuration TUF roots
    (both config_root and director_root) via environment variables.

    Returns:
        JSON string of the signed TUF root document

    """
    root_content = _build_tuf_root()
    signed_root = sign_tuf_document(root_content)
    return json.dumps(signed_root, separators=(",", ":"))


# =============================================================================
# TUF Metadata Builders
# =============================================================================
#
# These functions build the various TUF metadata documents needed for Remote
# Configuration. They are used by both the tracer-facing mock (in _remote_config.py)
# and the agent-facing backend (in rc_response_builder.py).
#

DEFAULT_OPAQUE_BACKEND_STATE = "eyJmb28iOiAiYmFyIn0="  # base64('{"foo": "bar"}')
DEFAULT_EXPIRES = "3000-01-01T00:00:00Z"


def build_targets_content(
    version: int,
    targets: dict | None = None,
    opaque_backend_state: str = DEFAULT_OPAQUE_BACKEND_STATE,
    expires: str = DEFAULT_EXPIRES,
) -> dict:
    """Build the 'signed' content for TUF targets metadata.

    Args:
        version: The version number for this targets document
        targets: Dict mapping target paths to their metadata (hashes, length, custom)
        opaque_backend_state: Base64-encoded backend state string
        expires: Expiration timestamp

    Returns:
        The 'signed' portion of targets metadata (not yet wrapped with signatures)

    """
    return {
        "_type": "targets",
        "custom": {"opaque_backend_state": opaque_backend_state},
        "expires": expires,
        "spec_version": "1.0",
        "targets": targets if targets is not None else {},
        "version": version,
    }


def build_signed_targets(
    version: int,
    targets: dict | None = None,
    opaque_backend_state: str = DEFAULT_OPAQUE_BACKEND_STATE,
    expires: str = DEFAULT_EXPIRES,
) -> dict:
    """Build a complete signed TUF targets document.

    Args:
        version: The version number for this targets document
        targets: Dict mapping target paths to their metadata
        opaque_backend_state: Base64-encoded backend state string
        expires: Expiration timestamp

    Returns:
        Complete signed TUF targets document with signatures

    """
    content = build_targets_content(version, targets, opaque_backend_state, expires)
    return sign_tuf_document(content)


def build_snapshot_content(
    version: int,
    targets_json: bytes,
    expires: str = DEFAULT_EXPIRES,
) -> dict:
    """Build the 'signed' content for TUF snapshot metadata.

    Args:
        version: The version number for this snapshot
        targets_json: The serialized targets.json content (for hash computation)
        expires: Expiration timestamp

    Returns:
        The 'signed' portion of snapshot metadata

    """
    targets_hash = hashlib.sha256(targets_json).hexdigest()
    return {
        "_type": "snapshot",
        "expires": expires,
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


def build_timestamp_content(
    version: int,
    snapshot_json: bytes,
    expires: str = DEFAULT_EXPIRES,
) -> dict:
    """Build the 'signed' content for TUF timestamp metadata.

    Args:
        version: The version number for this timestamp
        snapshot_json: The serialized snapshot.json content (for hash computation)
        expires: Expiration timestamp

    Returns:
        The 'signed' portion of timestamp metadata

    """
    snapshot_hash = hashlib.sha256(snapshot_json).hexdigest()
    return {
        "_type": "timestamp",
        "expires": expires,
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
