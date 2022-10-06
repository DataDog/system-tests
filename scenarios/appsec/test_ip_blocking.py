# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import time
import json


from scenarios.remote_config.test_remote_configuration import rc_check_request
from utils import BaseTestCase, context, coverage, interfaces, proxies, released, rfc
from utils.tools import logger

with open("scenarios/appsec/rc_expected_requests_asm_data.json") as f:
    EXPECTED_REQUESTS = json.load(f)


@rfc("https://docs.google.com/document/d/1GUd8p7HBp9gP0a6PZmDY26dpGrS1Ztef9OYdbK3Vq3M/edit")
@released(cpp="?", dotnet="2.16.0", java="0.110.0", php="?", python="?", ruby="?", nodejs="?")
@coverage.basic
class Test_AppSecIPBlocking(BaseTestCase):
    """ A library should block requests from blocked IP addresses. """

    BLOCKED_IPS = ["10.0.0.1"]
    TENTATIVES_PER_IP = 3

    request_number = 0

    def test_blocked_ips(self):
        """ test blocked ips are enforced """

        def validate_rc_protocol(data):

            if self.request_number >= len(EXPECTED_REQUESTS):
                return True

            logger.info(f"validating rc request number {self.request_number}")
            rc_check_request(data, EXPECTED_REQUESTS[self.request_number], caching=True)
            self.request_number += 1

        interfaces.library.add_remote_configuration_validation(validator=validate_rc_protocol)

        for ip in self.BLOCKED_IPS:
            for _ in range(self.TENTATIVES_PER_IP):
                r = self.weblog_get(headers={"X-Forwarded-For": ip})
                if r.status_code == 403:
                    interfaces.library.assert_waf_attack(r, rule="blk-001-001")
                    break
                time.sleep(2.0)
            else:
                raise Exception(f"blocked IP {ip} is not enforced after {self.TENTATIVES_PER_IP} tries")
