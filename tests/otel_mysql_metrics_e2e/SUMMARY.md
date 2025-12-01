# MySQL OTEL Metrics E2E Test - Summary

## Files Created/Modified

### 1. Test Files
- **tests/otel_mysql_metrics_e2e/__init__.py** - Package init file
- **tests/otel_mysql_metrics_e2e/mysql_metrics.json** - MySQL metrics definition file (45 metrics, excluding the 4 specified metrics)
- **tests/otel_mysql_metrics_e2e/test_otel_mysql_metrics.py** - Main test implementation

### 2. OTEL Collector Configuration
- **utils/build/docker/otelcol-config-with-mysql.yaml** - OTEL Collector configuration for MySQL receiver

### 3. Scenario Updates
- **utils/_context/_scenarios/otel_collector.py** - Modified to support MySQL database type
- **utils/_context/_scenarios/__init__.py** - Added `otel_mysql_metrics_e2e` scenario

## Test Structure

The test class `Test_OTelMySQLMetricsE2E` includes:

1. **setup_main()** - Triggers MySQL operations and loads expected metrics
2. **test_metrics_collected()** - Verifies MySQL metrics are collected and sent to backend
3. **test_metrics_via_collector()** - Validates metrics via OTEL Collector
4. **test_metric_data_types()** - Validates metric data types (Gauge vs Sum)

## Excluded Metrics (as requested)
- mysql.replica.sql_delay
- mysql.replica.time_behind_source
- mysql.mysqlx_connections
- mysql.mysqlx_worker_threads

## Running the Test

To run this test:
```bash
./run.sh OTEL_MYSQL_METRICS_E2E
```

## Requirements

- DD_API_KEY environment variable (for the agent path)
- DD_API_KEY_3 and DD_APP_KEY_3 environment variables (for the collector path)
- Java OTEL library (test is marked as irrelevant for other libraries)

## Scenario Details

The test uses the new `OTEL_MYSQL_METRICS_E2E` scenario which:
- Uses the OTEL Collector with MySQL receiver
- Includes a MySQL database container
- Sends metrics to the Datadog backend via OTEL Collector
- Uses the `otelcol-config-with-mysql.yaml` configuration file

