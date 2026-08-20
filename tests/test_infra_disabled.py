# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Verify that the agent does not report infrastructure data on standalone billing scenarios.

Standalone billing products (AppSec, IAST, SCA, AI Guard) opt out of APM billing with
DD_APM_TRACING_ENABLED=false on the tracer side. That alone does not prevent the host from being
billed as an infra host: the agent must also run with DD_INFRASTRUCTURE_MODE=none, which disables
every check (cpu, memory, disk, io, load, uptime, file handles, container and process collection).
These tests assert the outcome of that mode: no infrastructure metric ever reaches the backend.
"""

from utils import features, interfaces, rfc, scenarios

# Paths used by the agent to submit metric series to the backend
AGENT_SERIES_PATHS = ("/api/v2/series", "/api/intake/metrics/v3/series")

# Metric prefixes that only the infrastructure checks produce. The agent keeps reporting its own
# internal metrics (datadog.agent.*, datadog.dogstatsd.*, datadog.trace_agent.*) and forwards custom
# metrics in this mode, so only the check-produced namespaces are relevant to infra billing.
INFRA_METRIC_PREFIXES = ("system.", "container.", "docker.", "kubernetes.", "process.", "ntp.")

# The agent flushes metrics every 15 seconds
AGENT_METRICS_FLUSH_TIMEOUT = 60


def _is_metrics_payload(data: dict) -> bool:
    if data["path"] not in AGENT_SERIES_PATHS:
        return False

    content = data["request"]["content"]
    return isinstance(content, dict) and len(content.get("series", [])) != 0


@rfc("https://datadoghq.atlassian.net/wiki/spaces/agent/pages/6319080743/APM+Standalone+Mode+Mode+Spec")
class BaseInfraDisabled:
    """The agent must not report any infrastructure metric when the infra product is disabled."""

    def setup_no_infra_metrics(self):
        # Metrics are flushed on an interval, so wait for the first payload instead of relying on
        # the fixed collection window: an empty interface would make the assertion vacuous.
        self.agent_has_flushed_metrics = interfaces.agent.wait_for(
            _is_metrics_payload, timeout=AGENT_METRICS_FLUSH_TIMEOUT
        )

    def test_no_infra_metrics(self):
        assert self.agent_has_flushed_metrics, (
            f"The agent did not submit any metric within {AGENT_METRICS_FLUSH_TIMEOUT}s, "
            "absence of infrastructure metrics can't be asserted"
        )

        infra_metrics = sorted(
            {
                metric["metric"]
                for _, metric in interfaces.agent.get_metrics()
                if metric.get("metric", "").startswith(INFRA_METRIC_PREFIXES)
            }
        )

        assert not infra_metrics, (
            f"The agent reported infrastructure metrics, the host will be billed as an infra host: {infra_metrics}"
        )


@features.appsec_apm_standalone
@scenarios.appsec_standalone
class Test_AppSecStandalone_InfraDisabled(BaseInfraDisabled):
    """AppSec standalone billing does not report infrastructure data."""


@features.appsec_apm_standalone
@scenarios.iast_standalone
class Test_IastStandalone_InfraDisabled(BaseInfraDisabled):
    """IAST standalone billing does not report infrastructure data."""


@features.appsec_apm_standalone
@scenarios.sca_standalone
class Test_SCAStandalone_InfraDisabled(BaseInfraDisabled):
    """SCA standalone billing does not report infrastructure data."""


@features.ai_guard_standalone
@scenarios.ai_guard_standalone
class Test_AIGuardStandalone_InfraDisabled(BaseInfraDisabled):
    """AI Guard standalone billing does not report infrastructure data."""


@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
class Test_AppSecAPMStandalone_InfraDisabled(BaseInfraDisabled):
    """AppSec with APM Standalone mode does not report infrastructure data."""


@features.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecStandaloneAPMStandalone_InfraDisabled(BaseInfraDisabled):
    """AppSec standalone billing with APM Standalone mode does not report infrastructure data."""
