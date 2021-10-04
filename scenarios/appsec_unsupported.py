from utils import BaseTestCase, interfaces, context
from utils.warmups import default_warmup


context.add_warmup(default_warmup)


class TestAppSecDeactivated(BaseTestCase):
    def test_no_attack_detected(self):
        """ Appsec does not catch any attack """
        r = self.weblog_get("/", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.assert_no_appsec_event(r)

        r = self.weblog_get("/waf", params={"attack": "<script>"})
        interfaces.library.assert_no_appsec_event(r)

    def test_unsupported_logs_present(self):
        pass  # TODO have a solid way to read logs
        # f = open("/app/logs/docker/weblog.log", "r")
        # logs = f.read()
        # assert "AppSec could not start because the current environment is not supported." in logs
