# FFE Fixture Snapshot

These files are copied from the canonical FFE fixture repository.

Canonical source: https://github.com/DataDog/ffe-system-test-data
Source commit: be2ab8372d9cce5c77fbb940266564e7b86ce83a

Do not edit these fixtures directly in system-tests. Add or update shared FFE behavior in
ffe-system-test-data first, then refresh this snapshot.

The weekly update workflow runs `python3 utils/scripts/update_ffe_fixtures.py` and opens a signed
draft test PR only when the server evaluator fixture contents change.
