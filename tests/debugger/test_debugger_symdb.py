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
        self._assert_debugger_controller_exists()

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

    def _assert_scopes_have_minimum_depth(self) -> None:
        """Validate that SymDB has at least 1 depth in scopes structure.
        This ensures file hashes upload functionality works properly.
        """

        def check_scope_depth(scope: dict, current_depth: int = 0) -> int:
            """Recursively check scope depth and return the maximum depth found."""
            max_depth = current_depth
            nested_scopes = scope.get("scopes", [])

            if nested_scopes:
                for nested_scope in nested_scopes:
                    nested_depth = check_scope_depth(nested_scope, current_depth + 1)
                    max_depth = max(max_depth, nested_depth)

            return max_depth

        found_scopes_with_depth = False

        for symbol in self.symbols:
            content = symbol.get("content", {})
            if isinstance(content, dict):
                root_scopes = content.get("scopes", [])
                for scope in root_scopes:
                    scope_depth = check_scope_depth(scope)
                    if scope_depth >= 1:
                        found_scopes_with_depth = True
                        break

                if found_scopes_with_depth:
                    break

        assert found_scopes_with_depth, (
            "SymDB scopes must have at least 1 depth (nested scopes) to support file hashes upload functionality. "
            "No scopes with nested structure were found in the symbol database."
        )

    ############ test ############
    def setup_symdb_upload(self):
        self._setup()

    @bug(context.library == "dotnet", reason="DEBUG-3298")
    def test_symdb_upload(self):
        self._assert()

    def setup_symdb_scope_depth(self):
        self._setup()

    @bug(context.library == "dotnet", reason="DEBUG-3298")
    def test_symdb_scope_depth(self):
        """Test that SymDB uploads contain scopes with at least 1 depth for file hashes functionality.
        This test ensures the SymDB structure supports the new file hashes upload feature.
        """
        self.collect()
        self.assert_rc_state_not_error()
        self._assert_symbols_uploaded()
        self._assert_scopes_have_minimum_depth()
