# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, interfaces, scenarios, rfc


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.rasp_shell_injection
@scenarios.appsec_rasp
class Test_Shi_UrlQuery:
    """ Shell Injection through query parameters """

    def setup_shi_get(self):
        self.r = weblog.get("/rasp/shi", params={"list_dir": "$(cat /etc/passwd 1>&2 ; echo .)"})

    def test_shi_get(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-100",
            {
                "resource": {"address": "server.sys.shell.cmd", "ls $(cat /etc/passwd 1>&2 ; echo .)"},
                "params": {"address": "server.request.query", "value": "$(cat /etc/passwd 1>&2 ; echo .)"},
            },
        )


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.rasp_shell_injection
@scenarios.appsec_rasp
class Test_Shi_BodyUrlEncoded:
    """ Shell Injection through a url-encoded body parameter """

    def setup_shi_post_urlencoded(self):
        self.r = weblog.post("/rasp/shi", data={"list_dir": "$(cat /etc/passwd 1>&2 ; echo .)"})

    def test_shi_post_urlencoded(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-100",
            {
                "resource": {"address": "server.sys.shell.cmd", "ls $(cat /etc/passwd 1>&2 ; echo .)"},
                "params": {"address": "server.request.query", "value": "$(cat /etc/passwd 1>&2 ; echo .)"},
            },
        )


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.rasp_shell_injection
@scenarios.appsec_rasp
class Test_Shi_BodyXml:
    """ Shell Injection through an xml body parameter """

    def setup_shi_post_xml(self):
        data = "<?xml version='1.0' encoding='utf-8'?><list_dir>$(cat /etc/passwd 1>&amp;2 ; echo .)</list_dir>"
        self.r = weblog.post("/rasp/shi", data=data, headers={"Content-Type": "application/xml"})

    def test_shi_post_xml(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-100",
            {
                "resource": {"address": "server.sys.shell.cmd", "ls $(cat /etc/passwd 1>&2 ; echo .)"},
                "params": {"address": "server.request.query", "value": "$(cat /etc/passwd 1>&2 ; echo .)"},
            },
        )


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.rasp_shell_injection
@scenarios.appsec_rasp
class Test_Shi_BodyJson:
    """ Shell Injection through a json body parameter """

    def setup_shi_post_json(self):
        """AppSec detects attacks in JSON body values"""
        self.r = weblog.post("/rasp/shi", json={"list_dir": "$(cat /etc/passwd 1>&amp;2 ; echo .)"})

    def test_shi_post_json(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-100",
            {
                "resource": {"address": "server.sys.shell.cmd", "ls $(cat /etc/passwd 1>&2 ; echo .)"},
                "params": {"address": "server.request.query", "value": "$(cat /etc/passwd 1>&2 ; echo .)"},
            },
        )
