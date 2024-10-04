import os
import random
import string

import pytest

from .core import ScenarioGroup
from .endtoend import EndToEndScenario


def _get_unique_id(replay: bool, host_log_folder: str) -> str:
    # as this Id will be used to get data published in AWS, it must be unique
    # and to be able to be used in replay mode, it must be saved in a file

    replay_file = f"{host_log_folder}/unique_id.txt"

    if replay:
        with open(replay_file, "r", encoding="utf-8") as f:
            unique_id = f.read()
    else:
        # pick a statistically unique id for the scenario
        unique_id = "".join(random.choices(string.hexdigits, k=16))
        with open(replay_file, "w", encoding="utf-8") as f:
            f.write(unique_id)

    return unique_id


def _check_aws_variables(scenario: EndToEndScenario):
    if not os.environ.get("SYSTEM_TESTS_AWS_ACCESS_KEY_ID"):
        pytest.exit(
            f"Error while starting {scenario.name}: AWS environment variables for authentication must be set on your "
            "local machine\nPlease set 'SYSTEM_TESTS_AWS_ACCESS_KEY_ID' using valid credentials for Datadog AWS "
            "Sandbox Account: 601427279990.\nCredentials can be refreshed by running:\n"
            "    source utils/scripts/aws_login.sh",
            1
        )

    if not os.environ.get("SYSTEM_TESTS_AWS_SECRET_ACCESS_KEY"):
        pytest.exit(
            f"Error while starting {scenario.name}: AWS environment variables for authentication must be set on your "
            "local machine\nplease set 'SYSTEM_TESTS_AWS_SECRET_ACCESS_KEY' using valid credentials for Datadog AWS "
            "Sandbox Account: 601427279990. Credentials can be refreshed by running:\n"
            "source utils/scripts/aws_login.sh",
            1
        )


class IntegrationsScenario(EndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "INTEGRATIONS",
            weblog_env={
                "DD_DBM_PROPAGATION_MODE": "full",
                "DD_TRACE_SPAN_ATTRIBUTE_SCHEMA": "v1",
                "AWS_ACCESS_KEY_ID": "my-access-key",
                "AWS_SECRET_ACCESS_KEY": "my-access-key",
            },
            include_postgres_db=True,
            include_cassandra_db=True,
            include_mongo_db=True,
            include_kafka=True,
            include_rabbitmq=True,
            include_mysql_db=True,
            include_sqlserver=True,
            doc="Spawns tracer, agent, and a full set of database. Test the intgrations of those databases with tracers",
            scenario_groups=[ScenarioGroup.INTEGRATIONS, ScenarioGroup.APPSEC, ScenarioGroup.ESSENTIALS],
        )

    def configure(self, config):
        super().configure(config)
        _check_aws_variables(self)
        self.unique_id = _get_unique_id(self.replay, self.host_log_folder)


class CrossedTracingLibraryScenario(EndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "CROSSED_TRACING_LIBRARIES",
            weblog_env={
                "DD_TRACE_API_VERSION": "v0.4",
                "AWS_ACCESS_KEY_ID": "my-access-key",
                "AWS_SECRET_ACCESS_KEY": "my-access-key",
            },
            include_kafka=True,
            include_buddies=True,
            include_rabbitmq=True,
            doc="Spawns a buddy for each supported language of APM",
            scenario_groups=[ScenarioGroup.INTEGRATIONS],
        )

        # Since we are using real AWS queues / topics, we need a unique message to ensure we aren't consuming messages
        # from other tests. This time hash is added to the message, test consumers only stops once finding the specific
        # message.
        self.unique_id = None

    def configure(self, config):
        super().configure(config)
        _check_aws_variables(self)
        self.unique_id = _get_unique_id(self.replay, self.host_log_folder)
