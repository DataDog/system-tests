from utils import rfc, features, scenarios, interfaces


# Some tracers emit the raw name, others normalize it to the env-var form. Accept either.
CONFIG_NAMES = ("appsec.agentic_onboarding", "DD_APPSEC_AGENTIC_ONBOARDING")


def _find_config() -> list[dict[str, object]]:
    """Return telemetry configuration entries for the agentic-onboarding signal."""
    return [conf for conf in interfaces.library.get_telemetry_configurations() if conf.get("name") in CONFIG_NAMES]


@rfc("https://docs.google.com/document/d/1q1ZnDLFiKlLhGKljOCE8xTUOqdz325Rc3BcKjVan0VY/edit")
@features.appsec_agentic_onboarding
class Test_AppsecAgenticOnboarding:
    """RFC-1113: agentic-onboarding runtime signal (supersedes RFC-1110).

    `DD_APPSEC_AGENTIC_ONBOARDING` is an ordinary string config, reported verbatim with
    `origin` reflecting the source. No derived boolean, no AppSec-state gating.
    """

    @scenarios.telemetry_enhanced_config_reporting
    def test_reported_verbatim(self):
        """AppSec enabled + arbitrary value -> reported verbatim, origin=env_var."""
        entries = _find_config()
        assert entries, f"{CONFIG_NAMES} missing from telemetry"
        # Check every entry: prefork weblogs / config-change carrier can emit more than one.
        for entry in entries:
            assert entry.get("origin") == "env_var", f"Expected origin env_var, got: {entry}"
            assert entry["value"] == "MiXeD-Value_42", f"Expected verbatim value, got: {entry}"

    @scenarios.telemetry_app_started_products_disabled
    def test_reported_verbatim_appsec_disabled(self):
        """AppSec disabled + "true" -> still reported verbatim as "true", origin=env_var."""
        entries = _find_config()
        assert entries, f"{CONFIG_NAMES} missing from telemetry"
        for entry in entries:
            assert entry.get("origin") == "env_var", f"Expected origin env_var, got: {entry}"
            assert entry["value"] == "true", f"Expected verbatim value 'true', got: {entry}"

    @scenarios.default
    def test_reported_when_unset(self):
        """Flag absent -> still reported with empty value and origin=default."""
        entries = _find_config()
        assert entries, f"{CONFIG_NAMES} missing from telemetry"
        for entry in entries:
            assert entry.get("origin") == "default", f"Expected origin default, got: {entry}"
            assert entry["value"] == "", f"Expected empty string value, got: {entry}"
