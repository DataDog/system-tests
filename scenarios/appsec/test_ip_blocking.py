# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

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
    """
    A library should block requests from blocked IP addresses.

    This scenario is a sequence of several stages. A different set of IPs is blocked for each stage.
    """

    BLOCKED_IPS = [
        [],  # Stage 0: no config
        ["10.0.0.1"],  # Stage 1: initial config
        ["10.0.0.1"],  # Stage 2: modified initial config (different expiration)
    ]
    TENTATIVES_PER_IP = 3

    request_number = 0


    def test_blocked_ips(self):
        """ test blocked ips are enforced """

        test = interfaces.current_test()

        def check_enforced_blocking(expected_blocked_ips):
            enforced_blocking = [0] * len(expected_blocked_ips)

            for ip in expected_blocked_ips:
                for i in range(self.TENTATIVES_PER_IP):
                    r = self.weblog_get(headers={"X-Forwarded-For": ip})
                    if r.status_code == 403:
                        interfaces.library.assert_appsec_trigger(r, rule="blk-001-001", test=test)
                        enforced_blocking[i % len(expected_blocked_ips)] += 1
                        break

            missed_blocking = [ip for ip, count in zip(expected_blocked_ips, enforced_blocking) if count == 0]
            assert not missed_blocking, f"blocked IPs are not enforced after {self.TENTATIVES_PER_IP} tries"

        def validate(data):
            """ Method called when the library calls the remote config endpoint. """
            logger.info(f"validating rc request number {self.request_number}")
            if self.request_number >= len(self.BLOCKED_IPS):
                return True

            if self.request_number >= len(EXPECTED_REQUESTS):
                return True

            rc_check_request(data, EXPECTED_REQUESTS[self.request_number], caching=True)

            check_enforced_blocking(self.BLOCKED_IPS[self.request_number])

            self.request_number += 1

        interfaces.library.add_remote_configuration_validation(validator=validate)
