# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, irrelevant
from utils.warmups import default_warmup

context.add_warmup(default_warmup)


class Test_Misc(BaseTestCase):
    """ Check that traces are reported for mongodb clients """

    def test_main(self):
        r = self.weblog_get("/trace/mongo")
        interfaces.library.assert_trace_exists(r)
