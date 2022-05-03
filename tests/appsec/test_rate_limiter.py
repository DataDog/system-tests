# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import coverage, rfc


@rfc("https://docs.google.com/document/d/1X64XQOk3N-aS_F0bJuZLkUiJqlYneDxo_b8WnkfFy_0")
@coverage.not_implemented
class Test_Main:
    """ Rate limitier """
