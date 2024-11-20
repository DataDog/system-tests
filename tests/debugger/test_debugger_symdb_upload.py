# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import os

from utils import features, scenarios
from utils import remote_config as rc
from utils import interfaces

_DEBUGGER_PATH = "/api/v2/debugger"

@features.debugger
@scenarios.debugger_symdb
class Test_Debugger_SymDb:

    def _setup(self):
        self.rc_state = rc.send_symdb_command()

    def _get_tracer_data(self):
        return list(interfaces.agent.get_data(_DEBUGGER_PATH))

    def setup_symdb_upload(self):
        self._setup()

    def test_symdb_upload(self):
        assert self._get_tracer_data(), "symbols were not uploaded"
