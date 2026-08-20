from utils import rfc, features, scenarios, interfaces


# Some tracers emit the raw name, others normalize it to the env-var form. Accept either.
CONFIG_NAMES = ("appsec.agentic_onboarding", "DD_APPSEC_AGENTIC_ONBOARDING")


def _effective_config() -> dict[str, object] | None:
    """Return the effective agentic-onboarding config entry, or None if absent.

    A tracer may report the same configuration key at more than one precedence
    (e.g. a seeded ``default`` entry alongside the ``env_var`` value). The telemetry
    ``seq_id`` orders those entries and the highest one is the value actually in
    effect. Selecting the max-``seq_id`` entry works both for tracers that emit a
    single entry and for those that emit one entry per precedence.
    """
    entries = [conf for conf in interfaces.library.get_telemetry_configurations() if conf.get("name") in CONFIG_NAMES]
    if not entries:
        return None
    return max(entries, key=lambda conf: conf.get("seq_id", 0))


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
        entry = _effective_config()
        assert entry is not None, f"{CONFIG_NAMES} missing from telemetry"
        assert entry.get("origin") == "env_var", f"Expected origin env_var, got: {entry}"
        assert entry["value"] == "MiXeD-Value_42", f"Expected verbatim value, got: {entry}"

    @scenarios.telemetry_app_started_products_disabled
    def test_reported_verbatim_appsec_disabled(self):
        """AppSec disabled + "true" -> still reported verbatim as "true", origin=env_var."""
        entry = _effective_config()
        assert entry is not None, f"{CONFIG_NAMES} missing from telemetry"
        assert entry.get("origin") == "env_var", f"Expected origin env_var, got: {entry}"
        assert entry["value"] == "true", f"Expected verbatim value 'true', got: {entry}"

    @scenarios.default
    def test_reported_when_unset(self):
        """Flag absent -> still reported with empty value and origin=default."""
        entry = _effective_config()
        assert entry is not None, f"{CONFIG_NAMES} missing from telemetry"
        assert entry.get("origin") == "default", f"Expected origin default, got: {entry}"
        assert entry["value"] == "", f"Expected empty string value, got: {entry}"
