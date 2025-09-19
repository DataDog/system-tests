import random
import string

import pytest

from .core import scenario_groups
from .endtoend import EndToEndScenario


def _get_unique_id(host_log_folder: str, *, replay: bool) -> str:
    # as this Id will be used to get data published in AWS, it must be unique
    # and to be able to be used in replay mode, it must be saved in a file

    replay_file = f"{host_log_folder}/unique_id.txt"

    if replay:
        with open(replay_file, encoding="utf-8") as f:
            unique_id = f.read()
    else:
        # pick a statistically unique id for the scenario
        unique_id = "".join(random.choices(string.hexdigits, k=16))
        with open(replay_file, "w", encoding="utf-8") as f:
            f.write(unique_id)

    return unique_id


class IntegrationsScenario(EndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "INTEGRATIONS",
            weblog_env={
                "DD_DBM_PROPAGATION_MODE": "full",
                "DD_TRACE_SPAN_ATTRIBUTE_SCHEMA": "v1",
                "DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED": "false",
                "AWS_ACCESS_KEY_ID": "my-access-key",
                "AWS_SECRET_ACCESS_KEY": "my-access-key",
                "DD_TRACE_INFERRED_PROXY_SERVICES_ENABLED": "true",
                "SYSTEM_TESTS_AWS_URL": "http://localstack-main:4566",
                "DD_IAST_CONTEXT_MODE": "GLOBAL",
            },
            include_postgres_db=True,
            include_cassandra_db=True,
            include_mongo_db=True,
            include_kafka=True,
            include_rabbitmq=True,
            include_mysql_db=True,
            include_sqlserver=True,
            include_localstack=True,
            include_elasticmq=True,
            include_otel_drop_in=True,
            doc=(
                "Spawns tracer, agent, and a full set of database. "
                "Test the integrations of those databases with tracers"
            ),
            scenario_groups=[scenario_groups.integrations, scenario_groups.appsec, scenario_groups.essentials],
        )

    def configure(self, config: pytest.Config):
        super().configure(config)
        self.unique_id = _get_unique_id(self.host_log_folder, replay=self.replay)


class AWSIntegrationsScenario(EndToEndScenario):
    unique_id: str = ""

    def __init__(
        self,
        name: str,
        *,
        doc: str = "Spawns tracer, and agent. Test AWS integrations.",
        include_kafka: bool = False,
        include_rabbitmq: bool = False,
        include_buddies: bool = False,
        include_localstack: bool = True,
        include_elasticmq: bool = True,
    ) -> None:
        super().__init__(
            name,
            weblog_env={
                "DD_TRACE_API_VERSION": "v0.4",
                "AWS_ACCESS_KEY_ID": "my-access-key",
                "AWS_SECRET_ACCESS_KEY": "my-access-key",
                "SYSTEM_TESTS_AWS_URL": "http://localstack-main:4566",
            },
            doc=doc,
            include_kafka=include_kafka,
            include_rabbitmq=include_rabbitmq,
            include_buddies=include_buddies,
            include_localstack=include_localstack,
            include_elasticmq=include_elasticmq,
            scenario_groups=[scenario_groups.integrations, scenario_groups.essentials],
        )

    def configure(self, config: pytest.Config):
        super().configure(config)
        self.unique_id = _get_unique_id(self.host_log_folder, replay=self.replay)


class CrossedTracingLibraryScenario(EndToEndScenario):
    unique_id: str = ""

    def __init__(self) -> None:
        super().__init__(
            "CROSSED_TRACING_LIBRARIES",
            include_kafka=True,
            include_buddies=True,
            include_rabbitmq=True,
            include_localstack=True,
            include_elasticmq=True,
            doc="Spawns a buddy for each supported language of APM, requires AWS authentication.",
            weblog_env={
                "SYSTEM_TESTS_AWS_URL": "http://localstack-main:4566",
                "SYSTEM_TESTS_AWS_SQS_URL": "http://elasticmq:9324",
            },
            scenario_groups=[scenario_groups.integrations, scenario_groups.essentials],
        )

    def configure(self, config: pytest.Config):
        super().configure(config)
        self.unique_id = _get_unique_id(self.host_log_folder, replay=self.replay)
