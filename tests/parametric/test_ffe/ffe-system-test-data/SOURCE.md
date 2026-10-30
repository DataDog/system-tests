# FFE Fixture Snapshot

These files are copied from the canonical FFE fixture repository.

Canonical source: https://github.com/DataDog/ffe-system-test-data
Source commit: caa6d1ac3e5fbda0ce57ef3ffff3772901f3f466

Do not edit these fixtures directly in system-tests. Add or update shared FFE behavior in
ffe-system-test-data first, then refresh this snapshot.

The weekly update workflow runs `python3 utils/scripts/update_ffe_fixtures.py` and opens a signed
draft test PR only when the server evaluator fixture contents change.
