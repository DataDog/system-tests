# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
from utils import context, weblog, interfaces, features, missing_feature, logger


# those tests are linked to unix_domain_sockets_support_for_traces only for UDS weblogs
optional_uds_feature = (
    features.unix_domain_sockets_support_for_traces if "uds" not in context.weblog_variant else features.not_reported
)


@optional_uds_feature
class Test_Backend:
    """Misc test around agent/backend communication"""

    def test_good_backend(self):
        """Agent reads and use DD_SITE env var"""
        self._assert_good_backend(expected_domain=context.dd_site)

    @staticmethod
    def _assert_good_backend(expected_domain: str, excluded_sub_domains: tuple[str, ...] = ()) -> None:
        # agent performs some requests to perform a connectivity check
        # those requests use those 4 domains, regardless the value of DD_SITE
        # https://docs.datadoghq.com/agent/configuration/network/?site=us5
        connectivity_check_hosts = (
            "apt.datadoghq.com",
            "install.datadoghq.com",
            "yum.datadoghq.com",
            "keys.datadoghq.com",
        )

        for data in interfaces.agent.get_data():
            host: str = data["host"]

            # agent uses FQDN for almost all queries (same domain, but with a tailing dot).
            # but if for some reason, the connectivity fails, then the agent fallbacks to non-FQDN.
            # we cannot enforce FQDN assertion in this test, as connectivity fails may happen randomly.
            # we strip any tailing dot in the observed host for the test.
            host = host.rstrip(".")

            if host.startswith(excluded_sub_domains):
                logger.debug(f"{data['log_filename']} host: {host} -> ignored subdomain")
                continue

            if host in connectivity_check_hosts:
                logger.debug(f"{data['log_filename']} host: {host} -> connectivity host, ignored")
                continue

            domain: str = host[-len(expected_domain) :]

            if not domain.endswith(expected_domain):
                logger.error(f"{data['log_filename']} host: {host}")
                raise ValueError(f"Message {data['log_filename']} uses domain {domain} instead of {expected_domain}")

            logger.info(f"{data['log_filename']} host: {host}")


@optional_uds_feature
class Test_Library:
    """Misc test around library/agent communication"""

    def setup_receive_request_trace(self):
        self.r = weblog.get("/")

    def test_receive_request_trace(self):
        """Basic test to verify that libraries sent traces to the agent"""
        interfaces.library.assert_receive_request_root_trace()
