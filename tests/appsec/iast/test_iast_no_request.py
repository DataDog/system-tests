# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import missing_feature, interfaces, coverage, released

@released(dotnet="?", golang="?", nodejs="?")
@released(php_appsec="?", python="?", ruby="?", cpp="?")
@released(
    java={"spring-boot": "1.3.0", "spring-boot-jetty": "1.3.0", "spring-boot-openliberty": "1.3.0", "*": "?"},
)
@coverage.basic
class TestIastNoRequest:
    """ IAST deals with vulnerabilities outside of requests """

    @missing_feature(reason="Need to implement span creation")
    def test_span_creation(self):
        """ IAST creates a new span when no request is active """

        for _, span in interfaces.library.get_root_spans():
            if "_dd.iast.json" in span.get("meta", {}):
                if span.get("type", "") == "vulnerability":
                    return

        raise Exception("Did not find any span if IAST data and type == vulnerability")
