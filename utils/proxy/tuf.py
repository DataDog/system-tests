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
