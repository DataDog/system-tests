# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
import os
from pathlib import Path
from tests.fuzzer.tools._tools import cached_property


class _Data:
    def __init__(self):
        self.header_valid_list = "!#$%&'*+-.0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ^_`abcdefghijklmnopqrstuvwxyz|~"

    @cached_property
    def _data_path(self):
        return os.path.realpath(os.path.join(str(Path.cwd()), str(Path(__file__).parent)))

    @cached_property
    def blns(self):
        return json.load(open(os.path.join(self._data_path, "blns.json"), "r", encoding="utf-8"))

    @cached_property
    def re2_regexs(self):
        return [item["Pattern"] for item in self.re2_regexs_with_metadata]

    @cached_property
    def re2_regexs_with_metadata(self):
        return json.load(open(os.path.join(self._data_path, "regex.json"), "r", encoding="utf-8"))
