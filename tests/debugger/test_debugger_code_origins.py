# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2025 Datadog, Inc.

from utils import rfc
import tests.debugger.utils as debugger

from utils import (
    context,
    scenarios,
    features,
    bug,
    missing_feature
)

from utils.tools import logger

@rfc("https://docs.google.com/document/d/1lhaEgBGIb9LATLsXxuKDesx4BCYixOcOzFnr4qTTemw/edit?pli=1&tab=t.0#heading=h.o5gstqo08gu5")
@features.debugger
@scenarios.debugger_code_origins
class Test_Debugger_Code_Origins(debugger._Base_Debugger_Test):
    ############ setup ############
    def _setup(self):
        self.initialize_weblog_remote_config()

        ### prepare probes
        probes = debugger.read_probes("probe_status_spandecoration")
        self.set_probes(probes)

        self.send_rc_probes()
        self.wait_for_all_probes_installed()
        # self.send_weblog_request("/debugger/pii")
        self.wait_for_all_probes_emitting()

    ############ test ############
    def setup_code_origin_present(self):
        self._setup()

    @bug(context.library == "python@2.16.0", reason="DEBUG-3127")
    @bug(context.library == "python@2.16.1", reason="DEBUG-3127")
    @missing_feature(context.library == "ruby", reason="Not yet implemented")
    @missing_feature(context.library == "nodejs", reason="Not yet implemented")
    def test_code_origin_present(self):
        self.collect()

        self.assert_setup_ok()
        self.assert_rc_state_not_error()

        # TODO: Finish asserts, this is just a placeholder.
        for probe_id in self.probe_ids:
            base = self.probe_snapshots.get(probe_id, None)
            _ = base
