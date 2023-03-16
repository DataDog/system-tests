# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, context, bug, missing_feature, scenarios


@missing_feature(condition=context.library != "java", reason="Endpoint is not implemented on weblog")
@scenarios.dsm
class Test_Dsm:
    """ Verify that a cassandra span is created """

    def setup_main(self):
        print("setting up dsm test")
        self.r = weblog.get("/dsm")

    def test_main(self):
        print("running dsm test")
        print(self.r)
        assert(self.r.content == "ok")
