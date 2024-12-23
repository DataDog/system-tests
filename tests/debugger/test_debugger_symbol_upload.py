# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger
from utils import scenarios, features, bug, missing_feature, context, remote_config

@features.debugger
@scenarios.debugger_symbol_upload
class Test_Debugger_Symbol_Upload(debugger._Base_Debugger_Test):
    ############ setup ############
    def _setup(self):
        self.initialize_weblog_remote_config()
        
        # Send RC command to enable symbol uploads
        self.rc_state = remote_config.rc_state
        self.rc_state.set_config(
            "datadog/2/LIVE_DEBUGGING_SYMBOL_DB/symDb/config",
            {"upload_symbols": "true"}
        ).apply()

    ############ assert ############
    def _assert(self):
        self.collect()
        
        # Basic assertions
        self.assert_setup_ok()
        self.assert_rc_state_not_error()
        
        # Verify symbols were uploaded
        self._validate_symbol_uploads()

    def _validate_symbol_uploads(self):
        # TODO: Add validation logic once the symbol upload endpoint/format is defined
        # This could involve:
        # - Checking debugger input endpoint for symbol data
        # - Verifying format and content of uploaded symbols
        # - Confirming all expected symbols were included
        pass

    ############ test ############
    def setup_symbol_upload(self):
        self._setup()

    def test_symbol_upload(self):
        self._assert() 