from utils import rfc, features, scenarios, interfaces


CONFIG_KEY = "appsec.agentic_onboarding"
RAW_ENV_VAR = "DD_APPSEC_AGENTIC_ONBOARDING"


def _find_config(name: str) -> list[dict[str, object]]:
    """Return configuration entries whose name matches `name` exactly.

    The match is case-sensitive on purpose: intake normalization and retention
    mappings rely on the exact configuration name, so a tracer emitting the wrong
    wire casing must fail rather than pass.

    Per RFC-1110 the signal normally rides `app-started`, but when AppSec finishes
    starting after the first `app-started` it is delivered in the subsequent
    `app-client-configuration-change` event instead. `get_telemetry_configurations()`
    reads both carriers, so we intentionally accept either.
    """
    return [conf for conf in interfaces.library.get_telemetry_configurations() if conf.get("name") == name]


@rfc("https://docs.google.com/document/d/1l09G9w-VQGUy1RPZ41n2uwPDxHDGZNZ9pWWAvHg4f34/edit")
@features.appsec_agentic_onboarding
class Test_AppsecAgenticOnboarding:
    """RFC-1110: agentic-onboarding runtime signal.

    When `DD_APPSEC_AGENTIC_ONBOARDING` is set, the tracer reports a single boolean
    configuration entry `appsec.agentic_onboarding` in its telemetry (on `app-started`,
    or the subsequent `app-client-configuration-change`), with `origin=env_var` when
    the flag is injected as an environment variable. The reported value reflects
    whether AppSec is active at startup; the flag is presence-only (value never read),
    so the raw `DD_APPSEC_AGENTIC_ONBOARDING` key is never transmitted.
    """

    @scenarios.telemetry_enhanced_config_reporting
    def test_reported_true(self):
        """Flag set + AppSec enabled -> appsec.agentic_onboarding=true, origin=env_var."""
        entries = _find_config(CONFIG_KEY)
        assert entries, f"{CONFIG_KEY} missing from telemetry"
        entry = entries[-1]
        assert entry.get("origin") == "env_var", f"Expected origin env_var, got: {entry}"
        # native bool preferred; string fallback for cross-tracer compat. `is True`
        # rejects numeric 1 (1 == True in Python).
        assert entry["value"] is True or entry["value"] == "true", f"Expected boolean true, got: {entry}"
        # presence-only: only the derived boolean is sent, never the raw flag
        assert not _find_config(RAW_ENV_VAR), f"{RAW_ENV_VAR} must not be reported in telemetry"

    @scenarios.telemetry_app_started_products_disabled
    def test_reported_false(self):
        """Flag set + AppSec disabled -> appsec.agentic_onboarding=false, origin=env_var.

        The flag value in this scenario is "true" while AppSec is off, proving the
        reported boolean follows AppSec state, not the flag's literal value. The
        `origin=env_var` assertion ensures the entry is driven by the flag itself, not
        a default/product-state configuration that happens to be false.
        """
        entries = _find_config(CONFIG_KEY)
        assert entries, f"{CONFIG_KEY} missing from telemetry"
        entry = entries[-1]
        assert entry.get("origin") == "env_var", f"Expected origin env_var, got: {entry}"
        # `is False` rejects numeric 0 (0 == False in Python).
        assert entry["value"] is False or entry["value"] == "false", f"Expected boolean false, got: {entry}"
        assert not _find_config(RAW_ENV_VAR), f"{RAW_ENV_VAR} must not be reported in telemetry"
