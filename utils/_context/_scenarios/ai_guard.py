import os
import tarfile
import tempfile
from pathlib import Path

import pytest

from utils._context.containers import VCRCassettesContainer
from utils._logger import logger

from .endtoend import EndToEndScenario


class AIGuardScenario(EndToEndScenario):
    """AI Guard SDK testing scenario.

    Extends EndToEndScenario with support for generating VCR cassettes.
    When --generate-cassettes is passed, the VCR container records real API
    responses and they are extracted from the container into the logs directory.
    """

    def __init__(self, name: str, **kwargs):  # noqa: ANN003
        super().__init__(name, **kwargs)
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
