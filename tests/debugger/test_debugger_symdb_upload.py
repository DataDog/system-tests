# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
import os
import pprint

from utils import features, scenarios
from utils import remote_config as rc
from utils import interfaces

_CUR_DIR = os.path.dirname(os.path.abspath(__file__))
_DEBUGGER_PATH = "/api/v2/debugger"

@features.debugger
@scenarios.debugger_symdb_upload
class Test_Debugger_SymDb_Upload:

    def _setup(self):
        self.rc_state = rc.send_symdb_command()

    def _assert(self):
        with open(os.path.join(_CUR_DIR, "symdb/", "upload.json"), "r", encoding="utf-8") as f:
            return json.load(f)

    def _get_tracer_data(self):
        return list(interfaces.agent.get_data(_DEBUGGER_PATH))

    def setup_symdb_upload(self):
        self._setup()

    def test_symdb_upload(self):
        self._assert()
        pprint.pprint(self._get_tracer_data())

