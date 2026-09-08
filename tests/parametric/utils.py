import pytest

from utils import context

parametrize = pytest.mark.parametrize

# Minimum test agent version that supports client-side stats according to the spec
MIN_AGENT_VERSION_FOR_CSS = "7.65.0"


def enable_tracestats(
    sample_rate: float | None = None, extra_env: dict[str, str] | None = None
) -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_STATS_COMPUTATION_ENABLED": "true",  # reference, dotnet, python, golang
        "DD_TRACE_TRACER_METRICS_ENABLED": "true",  # java
    }
    if context.library == "golang" and context.library.version < "v1.55.0":
        env["DD_TRACE_FEATURES"] = "discovery"
    if sample_rate is not None:
        assert 0 <= sample_rate <= 1.0
        env.update({"DD_TRACE_SAMPLE_RATE": str(sample_rate)})
    if extra_env is not None:
        env.update(extra_env)

    return parametrize("library_env", [env])
