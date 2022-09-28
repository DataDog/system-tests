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
@released(cpp="?", dotnet="2.16.0", java="?", php="?", python="?", ruby="?", nodejs="?")
@coverage.basic
class Test_AppSecIPBlocking(BaseTestCase):
    """ A library should block requests from blocked IP addresses. """

    request_number = 0

    def test_tracer_update_sequence(self):
        """ test update sequence, based on a scenario mocked in the proxy """

        # TODO issue requests from blocked IP addresses

        def validate(data):
            """ Helper to validate config request content """
            logger.info(f"validating request number {self.request_number}")
            if self.request_number >= len(EXPECTED_REQUESTS):
                return True

            rc_check_request(data, EXPECTED_REQUESTS[self.request_number], caching=True)

            self.request_number += 1

        interfaces.library.add_remote_configuration_validation(validator=validate)
