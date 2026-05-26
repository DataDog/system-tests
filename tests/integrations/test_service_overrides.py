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

    # [DIAG do-not-merge] number of attempts to amplify the ~2% stall rate.
    # With 100 attempts the chance of seeing at least one stall per CI run is ~87%.
    _DIAG_ATTEMPTS = 100

    def setup_sql_srv_src(self):
        # [DIAG do-not-merge] loop the request to amplify the stall reproduction rate.
        # Each attempt uses timeout=30 (vs the usual 5) so we can see whether the request
        # eventually completes after the stall, and what the true elapsed time was.
        self.responses = []
        for i in range(self._DIAG_ATTEMPTS):
            t0 = time.monotonic()
            r = weblog.get("/rasp/sqli?user_id=1", timeout=30)
            elapsed = time.monotonic() - t0
            self.responses.append((i, r, elapsed))
        # Keep the original-shape attribute so the legacy assertion below still has something
        # to look at (we point it at the last response).
        self.r = self.responses[-1][1]

    def test_sql_srv_src(self):
        # [DIAG do-not-merge] surface every attempt that stalled or failed.
        slow = [(i, r, e) for (i, r, e) in self.responses if r.status_code != 200 or e > 1.0]
        logger.warning(f"[DIAG] /rasp/sqli stall summary: {len(slow)}/{len(self.responses)} slow-or-failed")
        for i, r, e in slow:
            rid = r.get_rid() if r.status_code is not None else "<no-rid>"
            logger.warning(f"[DIAG]   iter={i} status={r.status_code} elapsed={e:.3f}s rid={rid}")
        # Surface a stall as a test failure so CI flags the run and we collect artifacts.
        assert not slow, f"{len(slow)} stalls detected across {len(self.responses)} attempts"

        # Original assertions retained against the last response so we still validate the feature
        # whenever no stall occurs.
        assert self.r.status_code == 200

        srv_src_found = False
        for _, _, span in interfaces.library.get_spans(request=self.r, full_trace=True):
            if span.get("type") == "sql" and span.get("meta", {}).get("_dd.svc_src"):
                srv_src_found = True
                break

        assert srv_src_found, "Expected at least one SQL span to have _dd.svc_src set"
