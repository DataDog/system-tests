# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import os
import gzip
import json
import tests.debugger.utils as debugger
from utils import features, scenarios
from utils import remote_config as rc
from jsonschema import Draft7Validator


@features.debugger
@scenarios.debugger_symdb
class Test_Debugger_SymDb(debugger._Base_Debugger_Test):
    ############ setup ############
    def _setup(self):
        self.rc_state = rc.send_symdb_command()

    ############ assert ############
    def _assert(self):
        self.collect()
        self.assert_rc_state_not_error()
        self._assert_symbols_uploaded()

    def _assert_symbols_uploaded(self):
        assert len(self.symbols) > 0, "No symbol files were found"

        symbol_type = {
            "type": "object",
            "required": ["line", "name", "symbol_type", "type"],
            "properties": {
                "language_specifics": {"type": "object"},
                "line": {"type": "integer"},
                "name": {"type": "string"},
                "symbol_type": {"type": "string"},
                "type": {"type": ["string", "null"]},
            },
        }

        scope_type = {
            "type": "object",
            "required": ["end_line", "scope_type", "source_file", "start_line"],
            "properties": {
                "end_line": {"type": "integer"},
                "language_specifics": {"type": ["object", "null"]},
                "name": {"type": ["string", "null"]},
                "scope_type": {"type": "string"},
                "scopes": {"type": ["array", "null"], "items": {"$ref": "#/definitions/scope"}},
                "source_file": {"type": "string"},
                "start_line": {"type": "integer"},
                "symbols": {"type": ["array", "null"], "items": {"$ref": "#/definitions/symbol"}},
            },
        }

        schema = {
            "type": "object",
            "required": ["env", "language", "scopes", "service", "version"],
            "properties": {
                "env": {"type": "string", "const": "system-tests"},
                "language": {"type": "string"},
                "scopes": {"type": "array", "items": {"$ref": "#/definitions/scope"}},
                "service": {"type": "string", "const": "weblog"},
                "version": {"type": "string", "const": "1.0.0"},
            },
            "definitions": {"scope": scope_type, "symbol": symbol_type},
        }

        validator = Draft7Validator(schema)

        for file_path in self.symbols:
            assert file_path.endswith(".gz"), f"Symbol file {file_path} is not a .gz file"

            try:
                with gzip.open(file_path, "rb") as f:
                    content = json.loads(f.read().decode("utf-8"))
                    validation_errors = list(validator.iter_errors(content))
                    assert not validation_errors, f"Schema validation errors in {file_path}:\n" + "\n".join(
                        f"- {error.message} (at path: {' -> '.join(str(p) for p in error.path)})"
                        for error in validation_errors
                    )
            except gzip.BadGzipFile:
                assert False, f"File {file_path} is not a valid gzip archive"
            except json.JSONDecodeError:
                assert False, f"File {file_path} does not contain valid JSON"

    ############ test ############
    def setup_symdb_upload(self):
        self._setup()

    def test_symdb_upload(self):
        self._assert()
