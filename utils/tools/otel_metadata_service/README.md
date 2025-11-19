# OTel PostgreSQL Metadata Service

**Standalone FastAPI service** for fetching and querying OpenTelemetry PostgreSQL receiver metadata from GitHub.

## Overview

This service provides REST API endpoints to fetch and parse OpenTelemetry Collector Contrib PostgreSQL receiver metadata from GitHub. It's designed for testing and development scenarios where you need programmatic access to OTel metadata definitions.

**No Rapid dependencies required!** This is a pure FastAPI service that runs anywhere.

## Features

- ✅ Fetch PostgreSQL receiver metadata from GitHub
- ✅ Parse YAML metadata into structured Python dictionaries
- ✅ Query specific metrics, attributes, and events
- ✅ Filter enabled vs disabled metrics
- ✅ Support for specific commit SHAs
- ✅ RESTful API with FastAPI
- ✅ Interactive API documentation (Swagger UI & ReDoc)
- ✅ No external dependencies on Rapid or monorepo

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python main.py

# Visit the interactive docs
# http://localhost:8080/docs
```

## Dependencies

```
httpx>=0.24.0      # HTTP client for GitHub
pyyaml>=6.0        # YAML parser
fastapi>=0.104.0   # Web framework
uvicorn>=0.24.0    # ASGI server
pydantic>=2.0.0    # Data validation
```

## REST API Endpoints

The service exposes the following REST API endpoints:

### Core Endpoints

- `GET /` - Service information
- `GET /health` - Health check

### Metrics Endpoints

| Endpoint | Description | Example |
|----------|-------------|---------|
| `GET /api/v1/metrics` | Get all PostgreSQL metrics | `curl http://localhost:8080/api/v1/metrics` |
| `GET /api/v1/metrics/enabled` | Get only enabled metrics | `curl http://localhost:8080/api/v1/metrics/enabled` |
| `GET /api/v1/metrics/{metric_name}` | Get specific metric | `curl http://localhost:8080/api/v1/metrics/postgresql.backends` |

### Metadata Endpoints

| Endpoint | Description | Example |
|----------|-------------|---------|
| `GET /api/v1/resource-attributes` | Get resource attributes | `curl http://localhost:8080/api/v1/resource-attributes` |
| `GET /api/v1/attributes` | Get attributes | `curl http://localhost:8080/api/v1/attributes` |
| `GET /api/v1/events` | Get events | `curl http://localhost:8080/api/v1/events` |
| `GET /api/v1/metadata/full` | Get complete metadata file | `curl http://localhost:8080/api/v1/metadata/full` |

### Query Parameters

All endpoints support an optional `commit_sha` query parameter:

```bash
curl "http://localhost:8080/api/v1/metrics?commit_sha=270e3cb8cdfe619322be1af2b49a0901d8188a9c"
```

## Usage Examples

### Using curl

```bash
# Get all metrics
curl http://localhost:8080/api/v1/metrics | jq

# Get enabled metrics only
curl http://localhost:8080/api/v1/metrics/enabled | jq

# Get a specific metric
curl http://localhost:8080/api/v1/metrics/postgresql.backends | jq

# Get with custom commit SHA
curl "http://localhost:8080/api/v1/metrics?commit_sha=abc123" | jq

# Get events
curl http://localhost:8080/api/v1/events | jq
```

### Using Python (httpx)

```python
import httpx

# Create a client
client = httpx.Client(base_url="http://localhost:8080")

# Get all metrics
response = client.get("/api/v1/metrics")
metrics = response.json()
print(f"Found {len(metrics)} metrics")

# Get a specific metric
response = client.get("/api/v1/metrics/postgresql.backends")
metric = response.json()
print(f"Description: {metric['description']}")

# Get enabled metrics only
response = client.get("/api/v1/metrics/enabled")
enabled = response.json()
print(f"Enabled: {len(enabled)}")
```

### Direct Python Usage (No Server)

```python
from otel_metadata_fetcher import OTelMetadataFetcher

# Using context manager
with OTelMetadataFetcher() as fetcher:
    # Get all metrics
    metrics = fetcher.get_metrics()
    
    # Get enabled metrics only
    enabled = fetcher.get_enabled_metrics()
    
    # Get a specific metric
    backends_metric = fetcher.get_metric_by_name("postgresql.backends")
    
    # Get resource attributes
    attrs = fetcher.get_resource_attributes()
```

### Interactive Testing

Visit **http://localhost:8080/docs** for:
- ✨ Interactive API playground
- 📝 Try out each endpoint in your browser
- 📋 See request/response schemas
- 🎯 Test with different parameters

See `example_usage.py` for more detailed examples.

## Source Data

The metadata is fetched from the OpenTelemetry Collector Contrib repository:

**URL Pattern:**
```
https://raw.githubusercontent.com/open-telemetry/opentelemetry-collector-contrib/{commit_sha}/receiver/postgresqlreceiver/metadata.yaml
```

**Default Commit:** `270e3cb8cdfe619322be1af2b49a0901d8188a9c`

**Live URL:** [https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/270e3cb8cdfe619322be1af2b49a0901d8188a9c/receiver/postgresqlreceiver/metadata.yaml](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/270e3cb8cdfe619322be1af2b49a0901d8188a9c/receiver/postgresqlreceiver/metadata.yaml)

## Running the Service

```bash
# From the service directory
python main.py
```

The service will start and listen on the configured Rapid port.

## Testing

Run the example script to test the fetcher:

```bash
python example_usage.py
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                 MCP Client                          │
│          (Cursor, CLI tool, etc.)                   │
└───────────────────────┬─────────────────────────────┘
                        │
                        │ MCP Protocol
                        │
┌───────────────────────▼─────────────────────────────┐
│         Rapid MCP Handler (main.py)                 │
│                                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │  @otel_mcp.tool()                           │  │
│  │  - get_all_postgres_metrics()               │  │
│  │  - get_enabled_postgres_metrics()           │  │
│  │  - get_postgres_metric_by_name()            │  │
│  │  - get_postgres_resource_attributes()       │  │
│  │  - get_postgres_attributes()                │  │
│  │  - get_postgres_events()                    │  │
│  └──────────────────┬──────────────────────────┘  │
└─────────────────────┼──────────────────────────────┘
                      │
                      │ Uses
                      │
┌─────────────────────▼──────────────────────────────┐
│      OTelMetadataFetcher                           │
│      (otel_metadata_fetcher.py)                    │
│                                                    │
│  - Fetches from GitHub                            │
│  - Parses YAML                                    │
│  - Caches results                                 │
│  - Provides structured access                     │
└─────────────────────┬──────────────────────────────┘
                      │
                      │ HTTP GET
                      │
┌─────────────────────▼──────────────────────────────┐
│         GitHub Raw Content                         │
│  opentelemetry-collector-contrib repo             │
│  receiver/postgresqlreceiver/metadata.yaml        │
└────────────────────────────────────────────────────┘
```

## Metadata Structure

The PostgreSQL receiver metadata includes:

- **Metrics** (~40 metrics): Performance and usage metrics like `postgresql.backends`, `postgresql.db_size`, etc.
- **Resource Attributes**: Database name, table name, index name, schema name
- **Attributes**: Query attributes, network attributes, state information
- **Events**: Query samples and top queries with detailed attributes

## Location

This tool is located at:
```
system-tests/utils/tools/otel_metadata_service/
```

## Related Links

- [OpenTelemetry Collector Contrib](https://github.com/open-telemetry/opentelemetry-collector-contrib)
- [PostgreSQL Receiver Metadata](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/receiver/postgresqlreceiver/metadata.yaml)

## Support

For questions about this tool or system-tests, ask in [#apm-shared-testing](https://dd.enterprise.slack.com/archives/CHANNEL_ID).

---

**Note:** This is a standalone utility tool in system-tests, not a Rapid service. It has no external dependencies on Datadog infrastructure.

