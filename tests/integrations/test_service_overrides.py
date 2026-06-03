# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import time

from utils import context, weblog, interfaces, scenarios, features, irrelevant, logger


@features.service_override_source
@scenarios.integrations
@irrelevant(context.weblog_variant == "spring-boot-3-native", reason="/rasp/sqli endpoint is not available")
class Test_SqlServiceNameSource:
    """Verify that _dd.svc_src is set on SQL spans when the integration overrides the service name"""

    def setup_sql_srv_src(self):
        # [DIAG do-not-merge] timeout=30 (vs the usual 5) so the request can complete after a
        # stall and we can read the true elapsed time. No in-test looping — looping was suspected
        # of masking the bug by warming caches/threads.
        t0 = time.monotonic()
        self.r = weblog.get("/rasp/sqli?user_id=1", timeout=30)
        self.r_elapsed = time.monotonic() - t0

    def test_sql_srv_src(self):
        # [DIAG do-not-merge] log the elapsed time when the call was slow or failed, even if the
        # assertion below would still pass (e.g., status=200 but elapsed=4.5s).
        if self.r.status_code != 200 or self.r_elapsed > 1.0:
            rid = self.r.get_rid() if self.r.status_code is not None else "<no-rid>"
            logger.warning(
                f"[DIAG] /rasp/sqli stall: status={self.r.status_code} elapsed={self.r_elapsed:.3f}s rid={rid}"
            )
        # [DIAG do-not-merge] also fail on slow-but-200 so CI flags the run for artifact collection.
        assert self.r.status_code == 200, f"Got status {self.r.status_code} after {self.r_elapsed:.3f}s"
        assert self.r_elapsed <= 1.0, f"Stalled — request took {self.r_elapsed:.3f}s"

        srv_src_found = False
        for _, _, span in interfaces.library.get_spans(request=self.r, full_trace=True):
            if span.get("type") == "sql" and span.get("meta", {}).get("_dd.svc_src"):
                srv_src_found = True
                break

        assert srv_src_found, "Expected at least one SQL span to have _dd.svc_src set"
