# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import re
import tests.debugger.utils as debugger
from utils import features, scenarios, bug, context


@features.debugger_symdb
@scenarios.debugger_symdb
class Test_Debugger_SymDb(debugger.BaseDebuggerTest):
    ############ setup ############
    def _setup(self):
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

        def check_scope(scope):
            name = scope.get("name", "")
            if re.search(pattern, name):
                scope_type = scope.get("scope_type", "")
                return scope_type in ["CLASS", "class", "MODULE"]

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

    ############ test ############
    def setup_symdb_upload(self):
        self._setup()

    @bug(context.library == "dotnet", reason="DEBUG-3298")
    def test_symdb_upload(self):
        self._assert()
