# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""AAP smoke coverage with classic Agent infrastructure and native tracing."""

from ._core import DdTraceEndToEndScenario, scenario_groups


class SecuritySmoke(DdTraceEndToEndScenario):
    """AppSec payload carrier preservation through classic Agent infrastructure."""

    def __init__(self) -> None:
        super().__init__(
            "SECURITY_SMOKE",
            rc_api_enabled=True,
            iast_enabled=True,
            weblog_env={
                "DD_TELEMETRY_METRICS_ENABLED": "true",
                "DD_TELEMETRY_METRICS_INTERVAL_SECONDS": "2.0",
                "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
                "DD_API_SECURITY_SAMPLE_DELAY": "0.0",
            },
            scenario_groups=[scenario_groups.appsec],
        )
