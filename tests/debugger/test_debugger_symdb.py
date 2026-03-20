# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import re
import tests.debugger.utils as debugger
from utils import features, scenarios, context, missing_feature


@features.debugger_symdb
@scenarios.debugger_symdb
@missing_feature(
    context.library == "golang" and context.agent_version < "7.72.0-rc.1", reason="This feature relies on agent code"
)
class Test_Debugger_SymDb(debugger.BaseDebuggerTest):
    ############ setup ############
    def _setup(self):
        self.initialize_weblog_remote_config()
        self.send_rc_symdb()

    ############ assert ############
    def _assert(self):
        self.collect()
        self.assert_rc_state_not_error()
        self._assert_symbols_uploaded()

    def _assert_symbols_uploaded(self):
        assert len(self.symbols) > 0, "No symbol files were found"

        errors = []
        for symbol in self.symbols:
            error = symbol.get("system-tests-error")
            if error is not None:
                errors.append(
                    f"Error is: {error}, exported to file: {symbol.get('system-tests-file-path', 'No file path')}"
                )

        assert not errors, "Found system-tests-errors:\n" + "\n".join(f"- {err}" for err in errors)
        self._assert_symbols_have_depth()
        self._assert_debugger_controller_exists()

    def _assert_symbols_have_depth(self):
        has_depth = False

        for symbol in self.symbols:
            content = symbol.get("content", {})
            if isinstance(content, dict):
                scopes = content.get("scopes", [])
                for scope in scopes:
                    if scope.get("scopes", []):
                        has_depth = True
                        break

            if has_depth:
                break

        assert has_depth, "No symbols with at least 1 level deep (nested scopes) were found"

    def _assert_debugger_controller_exists(self):
        pattern = r"[Dd]ebugger[_]?[Cc]ontroller"

        def check_scope(scope: dict):
            name = scope.get("name", "")
            if re.search(pattern, name):
                scope_type = scope.get("scope_type", "")
                return scope_type in [
                    "CLASS",
                    "class",
                    "MODULE",
                    "struct",  # Go
                ]

            return any(check_scope(nested_scope) for nested_scope in scope.get("scopes", []))

        for symbol in self.symbols:
            content = symbol.get("content", {})
            if isinstance(content, dict):
                for scope in content.get("scopes", []):
                    if check_scope(scope):
                        return

        raise ValueError(
            "No scope containing debugger controller with scope_type CLASS or MODULE was found in the symbols"
        )

    def _assert_event_metadata(self):
        """Assert each /symdb/v1/input upload has the expected metadata fields
        in BOTH the event JSON and the gzipped attachment, and that they agree.

        Each request is a multipart with two parts: a gzipped attachment
        ("file") and a small JSON metadata blob ("event"). The event uses
        camelCase keys (uploadId/batchNum/attachmentSize) to match the rest
        of the EvP event schema; the attachment uses snake_case
        (upload_id/batch_num/final) to match the rest of the attachment
        scope schema (scope_type/source_file/...). The (uploadId, batchNum)
        in the event must equal (upload_id, batch_num) in the attachment.

        BaseDebuggerTest._collect_symdb_upload_events() and
        BaseDebuggerTest._collect_symbols() walk the same captured requests
        in the same order, so events[i] pairs with the attachment in
        symbols[i].
        """
        events = self.symdb_upload_events
        attachments = self.symbols
        assert events, "No event multipart parts were captured"
        assert attachments, "No attachment multipart parts were captured"
        assert len(events) == len(attachments), (
            f"event count ({len(events)}) does not match attachment count ({len(attachments)})"
        )

        required_event_fields = (
            "ddsource",
            "service",
            "version",
            "language",
            "runtimeId",
            "type",
            "uploadId",
            "batchNum",
            "final",
            "attachmentSize",
        )
        required_attachment_fields = ("upload_id", "batch_num", "final")

        for event, attachment_part in zip(events, attachments, strict=True):
            missing = [f for f in required_event_fields if f not in event]
            assert not missing, f"event missing fields {missing}: {event!r}"

            assert event["type"] == "symdb", f"type is not 'symdb': {event['type']!r}"
            assert isinstance(event["batchNum"], int), f"batchNum is not an integer: {event['batchNum']!r}"
            assert event["batchNum"] >= 1, f"batchNum is not >= 1: {event['batchNum']!r}"
            assert isinstance(event["final"], bool), f"final is not a boolean: {event['final']!r}"
            assert isinstance(event["attachmentSize"], int), (
                f"attachmentSize is not an integer: {event['attachmentSize']!r}"
            )
            assert event["attachmentSize"] > 0, f"attachmentSize is not > 0: {event['attachmentSize']!r}"
            assert "debugger" not in event, f"event must not nest fields under 'debugger': {event['debugger']!r}"

            # The attachment body must carry the same upload metadata at the
            # root, in snake_case to match the rest of the attachment schema.
            attachment = attachment_part.get("content", {})
            assert isinstance(attachment, dict), f"attachment is not a JSON object: {attachment!r}"
            missing_att = [f for f in required_attachment_fields if f not in attachment]
            assert not missing_att, f"attachment missing fields {missing_att}: keys={list(attachment.keys())}"

            assert attachment["upload_id"] == event["uploadId"], (
                f"attachment upload_id ({attachment['upload_id']!r}) "
                f"does not match event uploadId ({event['uploadId']!r})"
            )
            assert attachment["batch_num"] == event["batchNum"], (
                f"attachment batch_num ({attachment['batch_num']!r}) "
                f"does not match event batchNum ({event['batchNum']!r})"
            )
            assert isinstance(attachment["final"], bool), f"attachment final is not a boolean: {attachment['final']!r}"

    ############ test ############
    def setup_symdb_upload(self):
        self._setup()

    def test_symdb_upload(self):
        self._assert()

    def setup_event_metadata(self):
        self._setup()

    def test_event_metadata(self):
        self.collect()
        self.assert_rc_state_not_error()
        self._assert_event_metadata()
