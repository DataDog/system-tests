import os
import time

from .endtoend import EndToEndScenario


class PerformanceScenario(EndToEndScenario):
    def __init__(self, name: str, doc: str) -> None:
        super().__init__(
            name, doc=doc, appsec_enabled=self.appsec_enabled, use_proxy_for_agent=False, use_proxy_for_weblog=False
        )

    @property
    def appsec_enabled(self):
        return os.environ.get("DD_APPSEC_ENABLED") == "true"

    @property
    def host_log_folder(self):
        return "logs_with_appsec" if self.appsec_enabled else "logs_without_appsec"

    def get_warmups(self):
        result = super().get_warmups()
        result.append(self._extra_weblog_warmup)

        return result

    def _extra_weblog_warmup(self):
        from utils import weblog

        WARMUP_REQUEST_COUNT = 10  # noqa: N806
        WARMUP_LAST_SLEEP_DURATION = 3  # noqa: N806

        for _ in range(WARMUP_REQUEST_COUNT):
            weblog.warmup_request(timeout=10)
            time.sleep(0.6)

        time.sleep(WARMUP_LAST_SLEEP_DURATION)
