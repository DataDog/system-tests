from utils import rfc, features, scenarios, interfaces


# The runtime signal reported in the telemetry configuration list.
CONFIG_KEY = "appsec.agentic_onboarding"


def _find_config(name: str) -> list[dict]:
    """Return configuration entries matching `name` (case-insensitive).

    Per RFC-1110, the signal normally rides `app-started`, but when AppSec finishes
    starting after the first `app-started` it is delivered in the subsequent
    `app-client-configuration-change` event instead. `get_telemetry_configurations()`
    reads both carriers, so we intentionally accept either.
    """
    return [
        conf
        for conf in interfaces.library.get_telemetry_configurations()
        if conf.get("name", "").lower() == name.lower()
    ]


@rfc("https://docs.google.com/document/d/1l09G9w-VQGUy1RPZ41n2uwPDxHDGZNZ9pWWAvHg4f34/edit")
@features.appsec_agentic_onboarding
class Test_AppsecAgenticOnboarding:
    """RFC-1110: agentic-onboarding runtime signal.

    When `DD_APPSEC_AGENTIC_ONBOARDING` is set, the tracer reports a single boolean
    configuration entry `appsec.agentic_onboarding` in its telemetry (on `app-started`,
    or the subsequent `app-client-configuration-change`), with `origin=env_var` when
    the flag is injected as an environment variable. The reported value reflects
    whether AppSec is active at startup; the flag is presence-only (value never read).
    """

    @scenarios.telemetry_enhanced_config_reporting
    def test_reported_true(self):
        """Flag set + AppSec enabled -> appsec.agentic_onboarding=true, origin=env_var."""
        entries = _find_config(CONFIG_KEY)
        assert entries, f"{CONFIG_KEY} missing from telemetry"
        entry = entries[-1]
        assert entry.get("origin") == "env_var", f"Expected origin env_var, got: {entry}"
        assert entry["value"] in (True, "true"), f"Expected truthy value, got: {entry}"

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
        assert entry["value"] in (False, "false"), f"Expected falsy value, got: {entry}"
