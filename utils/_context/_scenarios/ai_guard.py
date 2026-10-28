import os
from pathlib import Path
import tarfile
import tempfile

import pytest

from ._core import EndToEndScenario, scenario_groups
from utils._context.constants import ContainerPorts, WeblogCategory
from utils._context.containers import VCRCassettesContainer
from utils._logger import logger


# Shared by every AI Guard scenario: the SDK on, AppSec and IAST off so nothing else drives the
# spans under test, and the endpoint pointed at the VCR container with keys the mock backend
# ignores. Each scenario adds only what it is there to exercise.
_AI_GUARD_WEBLOG_ENV = {
    "DD_APPSEC_ENABLED": "false",
    "DD_IAST_ENABLED": "false",
    "DD_AI_GUARD_ENABLED": "true",
    "DD_AI_GUARD_ENDPOINT": f"http://vcr_cassettes:{ContainerPorts.vcr_cassettes}/vcr/aiguard",
    "DD_API_KEY": "mock_api_key",
    "DD_APP_KEY": "mock_app_key",
}


class _AIGuardScenario(EndToEndScenario):
    """AI Guard SDK testing scenario.

    Extends EndToEndScenario with support for generating VCR cassettes.
    When --generate-cassettes is passed, the VCR container records real API
    responses and they are extracted from the container into the logs directory.
    """

    def __init__(self, name: str, **kwargs):  # noqa: ANN003
        super().__init__(name, weblog_categories=[WeblogCategory.dd_trace], **kwargs)
        self._generate_cassettes = False

    def configure(self, config: pytest.Config):
        self._generate_cassettes = getattr(config.option, "generate_cassettes", False)

        if self._generate_cassettes:
            self._configure_for_cassette_generation()

        super().configure(config)

    def _configure_for_cassette_generation(self):
        # Require real API keys and set them on the weblog container
        for key in ("DD_API_KEY", "DD_APP_KEY"):
            value = os.environ.get(key)
            if not value:
                pytest.exit(f"{key} is required to generate cassettes", 1)
            self.weblog_container.environment[key] = value

        # Switch VCR container to record mode (writable cassettes dir, no existing cassettes)
        for container in self.weblog_infra.get_containers():
            if isinstance(container, VCRCassettesContainer):
                container.set_generate_cassettes_mode()
                self._vcr_container = container
                break

    def post_setup(self, session: pytest.Session):
        if self._generate_cassettes:
            self._extract_cassettes_from_container()

        super().post_setup(session)

    def _extract_cassettes_from_container(self):
        """Extract recorded cassettes from the VCR container via docker cp."""
        dst = Path(self.host_log_folder) / "recorded_cassettes"
        dst.mkdir(parents=True, exist_ok=True)

        # docker cp returns a tar archive
        bits, _ = self._vcr_container.get_archive("/cassettes/aiguard")
        with tempfile.TemporaryFile() as tmp:
            for chunk in bits:
                tmp.write(chunk)
            tmp.seek(0)
            with tarfile.open(fileobj=tmp) as tar:
                tar.extractall(path=dst, filter="data")

        extracted = dst / "aiguard"
        if extracted.is_dir():
            cassettes = [f for f in extracted.iterdir() if f.suffix == ".json"]
            logger.stdout(f"Extracted {len(cassettes)} cassettes to ./{extracted}")
        else:
            logger.warning("No cassettes found in container at /cassettes/aiguard")


class AiGuard(_AIGuardScenario):
    def __init__(self) -> None:
        super().__init__(
            "AI_GUARD",
            other_weblog_containers=(VCRCassettesContainer,),
            appsec_enabled=False,
            weblog_env=_AI_GUARD_WEBLOG_ENV,
            doc="AI Guard SDK tests",
            scenario_groups=[scenario_groups.ai_guard],
        )


class AiGuardStandalone(_AIGuardScenario):
    def __init__(self) -> None:
        super().__init__(
            "AI_GUARD_STANDALONE",
            other_weblog_containers=(VCRCassettesContainer,),
            appsec_enabled=False,
            weblog_env={
                **_AI_GUARD_WEBLOG_ENV,
                "DD_APM_TRACING_ENABLED": "false",
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            },
            agent_env={
                "DD_INFRASTRUCTURE_MODE": "none",
            },
            doc="AI Guard standalone mode, with the infra product disabled on the agent",
            scenario_groups=[scenario_groups.ai_guard],
        )


class AiGuardTelemetry(_AIGuardScenario):
    def __init__(self) -> None:
        super().__init__(
            "AI_GUARD_TELEMETRY",
            other_weblog_containers=(VCRCassettesContainer,),
            appsec_enabled=False,
            weblog_env={
                **_AI_GUARD_WEBLOG_ENV,
                "DD_AI_GUARD_MAX_MESSAGES_LENGTH": "1",
                "DD_AI_GUARD_MAX_CONTENT_SIZE": "5",
            },
            doc="AI Guard telemetry tests with low truncation thresholds",
            scenario_groups=[scenario_groups.ai_guard],
        )


class AiGuardRedactionTelemetry(_AIGuardScenario):
    def __init__(self) -> None:
        super().__init__(
            "AI_GUARD_REDACTION_TELEMETRY",
            other_weblog_containers=(VCRCassettesContainer,),
            appsec_enabled=False,
            # Deliberately without the truncation thresholds AI_GUARD_TELEMETRY sets: the redaction
            # corpus is replayed from cassettes addressed by a hash of the request body, so a truncated
            # payload matches no cassette and never comes back with any replacement. The telemetry
            # flush intervals need no override, WeblogContainer already puts both at 2s.
            weblog_env=_AI_GUARD_WEBLOG_ENV,
            doc="AI Guard redaction telemetry tests, with untruncated payloads and exact metric counts",
            scenario_groups=[scenario_groups.ai_guard],
        )


class AiGuardRedactionDisabled(_AIGuardScenario):
    def __init__(self) -> None:
        super().__init__(
            "AI_GUARD_REDACTION_DISABLED",
            other_weblog_containers=(VCRCassettesContainer,),
            appsec_enabled=False,
            weblog_env={
                **_AI_GUARD_WEBLOG_ENV,
                # Global kill-switch: evaluations still run and findings are still reported, but the
                # redaction_replacements returned by the backend are never applied.
                "DD_AI_GUARD_REDACTION_ENABLED": "false",
            },
            doc="AI Guard with the sensitive data redaction kill-switch turned off",
            scenario_groups=[scenario_groups.ai_guard],
        )
