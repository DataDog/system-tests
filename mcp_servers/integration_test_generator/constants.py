METRIC_TYPES = {"sum", "gauge"}
GH_BASE_API = "https://api.github.com/repos/open-telemetry/opentelemetry-collector-contrib/"

# Path to reference test files
SYSTEM_TESTS_ROOT = Path(__file__).parent.parent.parent
POSTGRES_TEST_PATH = SYSTEM_TESTS_ROOT / "tests/otel_postgres_metrics_e2e/test_postgres_metrics.py"
MYSQL_TEST_PATH = SYSTEM_TESTS_ROOT / "tests/otel_mysql_metrics_e2e/test_otel_mysql_metrics.py"


# Integration-specific configurations
INTEGRATION_CONFIGS = {
    "redis": {
        "container_name": "redis_container",
        "smoke_test_operations": [
            'r = container.exec_run("redis-cli SET test_key test_value")',
            "logger.info(r.output)",
            'r = container.exec_run("redis-cli GET test_key")',
            "logger.info(r.output)",
            'r = container.exec_run("redis-cli INCR counter")',
            "logger.info(r.output)",
        ],
        "expected_smoke_metrics": [
            "redis.commands.processed",
            "redis.keys.expired",
            "redis.net.input",
            "redis.net.output",
        ],
    },
    "mysql": {
        "container_name": "mysql_container",
        "smoke_test_operations": [
            "r = container.exec_run(\"mysql -u root -ppassword -e 'CREATE DATABASE IF NOT EXISTS test_db;'\")",
            "r = container.exec_run(\"mysql -u root -ppassword test_db -e 'CREATE TABLE IF NOT EXISTS test_table (id INT PRIMARY KEY);'\")",
            "r = container.exec_run(\"mysql -u root -ppassword test_db -e 'INSERT INTO test_table VALUES (1);'\")",
            "logger.info(r.output)",
            "r = container.exec_run(\"mysql -u root -ppassword test_db -e 'SELECT * FROM test_table;'\")",
            "logger.info(r.output)",
        ],
        "expected_smoke_metrics": [
            "mysql.operations",
            "mysql.client.network.io",
            "mysql.commands",
        ],
    },
    "nginx": {
        "container_name": "nginx_container",
        "smoke_test_operations": [
            'r = container.exec_run("curl -s http://localhost/status")',
            "logger.info(r.output)",
        ],
        "expected_smoke_metrics": [
            "nginx.requests",
            "nginx.connections_accepted",
            "nginx.connections_handled",
        ],
    },
    "kafka": {
        "container_name": "kafka_container",
        "smoke_test_operations": [
            'r = container.exec_run("kafka-topics --create --topic test-topic --bootstrap-server localhost:9092")',
            "logger.info(r.output)",
            'r = container.exec_run("kafka-console-producer --topic test-topic --bootstrap-server localhost:9092", stdin="test message")',
        ],
        "expected_smoke_metrics": [
            "kafka.messages",
            "kafka.brokers",
        ],
    },
}
