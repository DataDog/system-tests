from utils import rfc, features, scenarios, interfaces


# Tracers report configuration entries under different naming conventions: some emit
# the raw dotted name (`appsec.agentic_onboarding`), others (e.g. Java) normalize it to
# the env-var form (`DD_APPSEC_AGENTIC_ONBOARDING`, uppercased with dots -> underscores).
# Both are the same configuration; accept either, just like other telemetry tests do for
# e.g. ["DD_APPSEC_ENABLED", "appsec.enabled"].
CONFIG_NAMES = ("appsec.agentic_onboarding", "DD_APPSEC_AGENTIC_ONBOARDING")


def _find_config() -> list[dict[str, object]]:
    """Return configuration entries for the agentic-onboarding signal.

    Matches either the raw name or the normalized env-var name (see `CONFIG_NAMES`).
    The match is case-sensitive on purpose: intake normalization and retention
    mappings rely on the exact configuration name, so a tracer emitting the wrong
    wire casing must fail rather than pass.

    Per RFC-1110 the signal normally rides `app-started`, but when AppSec finishes
    starting after the first `app-started` it is delivered in the subsequent
    `app-client-configuration-change` event instead. `get_telemetry_configurations()`
    reads both carriers, so we intentionally accept either.
    """
    return [conf for conf in interfaces.library.get_telemetry_configurations() if conf.get("name") in CONFIG_NAMES]


@rfc("https://docs.google.com/document/d/1l09G9w-VQGUy1RPZ41n2uwPDxHDGZNZ9pWWAvHg4f34/edit")
@features.appsec_agentic_onboarding
class Test_AppsecAgenticOnboarding:
    """RFC-1110: agentic-onboarding runtime signal.

    When `DD_APPSEC_AGENTIC_ONBOARDING` is set, the tracer reports a single boolean
    configuration entry (`appsec.agentic_onboarding`, or the normalized `DD_APPSEC_AGENTIC_ONBOARDING`
    name for tracers that normalize config keys) in its telemetry (on `app-started`, or the
    subsequent `app-client-configuration-change`), with `origin=env_var` when the flag is
    injected as an environment variable. The reported value reflects whether AppSec is
    active at startup; the flag is presence-only, i.e. the tracer never reads the env-var's
    literal value, it only derives the boolean from AppSec state.
    """

    @scenarios.telemetry_enhanced_config_reporting
    def test_reported_true(self):
        """Flag set + AppSec enabled -> agentic-onboarding config = true, origin=env_var."""
        entries = _find_config()
        assert entries, f"{CONFIG_NAMES} missing from telemetry"
        # Assert every reported entry is consistent rather than counting them: prefork /
        # multiprocess weblogs (uwsgi, php-fpm) and the app-client-configuration-change
        # carrier can legitimately emit more than one, so a count check would be flaky;
        # this still catches a contradictory or wrongly-sourced report.
        for entry in entries:
            assert entry.get("origin") == "env_var", f"Expected origin env_var, got: {entry}"
            # native bool preferred; string fallback for cross-tracer compat. `is True`
            # rejects numeric 1 (1 == True in Python).
            assert entry["value"] is True or entry["value"] == "true", f"Expected boolean true, got: {entry}"

    @scenarios.telemetry_app_started_products_disabled
    def test_reported_false(self):
        """Flag set + AppSec disabled -> appsec.agentic_onboarding=false, origin=env_var.

        The flag value in this scenario is "true" while AppSec is off, proving the
        reported boolean follows AppSec state, not the flag's literal value. The
        `origin=env_var` assertion ensures the entry is driven by the flag itself, not
        a default/product-state configuration that happens to be false.
        """
        entries = _find_config()
        assert entries, f"{CONFIG_NAMES} missing from telemetry"
        entry = entries[-1]
        assert entry.get("origin") == "env_var", f"Expected origin env_var, got: {entry}"
        # `is False` rejects numeric 0 (0 == False in Python).
        assert entry["value"] is False or entry["value"] == "false", f"Expected boolean false, got: {entry}"
