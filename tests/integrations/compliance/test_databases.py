from utils import logger, scenarios
from .utils import assert_required_keys, generate_compliance_report, load_schema

from tests.integrations.utils import BaseDbIntegrationsTestClass


class _BaseDatabaseComplianceTest(BaseDbIntegrationsTestClass):
    def get_spans(self, excluded_operations=(), operations=None):
        for db_operation, request in self.get_requests(excluded_operations, operations=operations):
            logger.debug(f"Validating {self.db_service}/{db_operation}")
            yield db_operation, self.get_span_from_tracer(request)
            yield db_operation, self.get_span_from_agent(request)

    def test_attributes(self):
        schema = load_schema("databases")

        all_missing = []
        all_deprecated = []

        for _db_operation, span in self.get_spans(excluded_operations=["procedure", "select_error"]):
            # print(f"Span found for {_db_operation}: {json.dumps(span, indent=2)}")

            missing, deprecated = assert_required_keys(span, schema)
            all_missing.extend(missing)
            all_deprecated.extend(deprecated)

        all_missing = sorted(set(all_missing))
        all_deprecated = sorted(set(all_deprecated))

        generate_compliance_report(
            category="database", name=self.db_service, missing=all_missing, deprecated=all_deprecated
        )

        if all_missing:
            raise AssertionError(f"Missing required attributes: {all_missing}")


@scenarios.integrations
class Test_Postgres(_BaseDatabaseComplianceTest):
    """Postgres compliance tests."""

    db_service = "postgresql"


@scenarios.integrations
class Test_MySql(_BaseDatabaseComplianceTest):
    """MySQL compliance tests."""

    db_service = "mysql"


@scenarios.integrations
class Test_MsSql(_BaseDatabaseComplianceTest):
    """MSSQL compliance tests."""

    db_service = "mssql"
