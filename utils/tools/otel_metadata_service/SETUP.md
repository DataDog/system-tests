# Quick Setup Guide

## What Was Created

Your Rapid MCP service now includes:

1. **`otel_metadata_fetcher.py`** - Core fetcher module to get PostgreSQL receiver metadata from GitHub
2. **`main.py`** - Updated with 6 MCP tools to expose the fetcher functionality
3. **`example_usage.py`** - Standalone example showing direct usage
4. **`test_otel_fetcher.py`** - Pytest test suite
5. **`requirements.txt`** - Dependencies (httpx, pyyaml)
6. **`README.md`** - Full documentation

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Or add to your project's dependencies:
```
httpx>=0.24.0
pyyaml>=6.0
```

### 2. Test the Fetcher Directly

```bash
cd /Users/quinna.halim/system-tests/utils/tools/otel_metadata_service
python example_usage.py
```

This will fetch and display:
- All PostgreSQL metrics
- Enabled metrics only
- Resource attributes
- Events
- Specific metric examples

### 3. Run Tests

```bash
pytest test_otel_fetcher.py -v
```

### 4. Start the Rapid Service

```bash
python main.py
```

The MCP tools will be available at:
```
/internal/unstable/federatedtesting/otel/postgres
```

## Available MCP Tools

Once the service is running, you can call these tools:

| Tool Name | Description | Parameters |
|-----------|-------------|------------|
| `get_all_postgres_metrics` | Get all PostgreSQL metrics | `commit_sha` (optional) |
| `get_enabled_postgres_metrics` | Get only enabled metrics | `commit_sha` (optional) |
| `get_postgres_metric_by_name` | Get specific metric | `metric_name` (required), `commit_sha` (optional) |
| `get_postgres_resource_attributes` | Get resource attributes | `commit_sha` (optional) |
| `get_postgres_attributes` | Get attributes | `commit_sha` (optional) |
| `get_postgres_events` | Get events | `commit_sha` (optional) |

## Example: Direct Python Usage

```python
from otel_metadata_fetcher import OTelMetadataFetcher

# Quick one-liner
from otel_metadata_fetcher import get_postgres_metrics
metrics = get_postgres_metrics()
print(f"Found {len(metrics)} metrics")

# Or use the class for more control
with OTelMetadataFetcher() as fetcher:
    # Get all metrics
    all_metrics = fetcher.get_metrics()
    
    # Get only enabled metrics
    enabled = fetcher.get_enabled_metrics()
    
    # Get a specific metric
    backends = fetcher.get_metric_by_name("postgresql.backends")
    print(backends)
```

## Example: MCP Tool Call (from Cursor or CLI)

```python
import httpx

response = httpx.post(
    "https://your-service/internal/unstable/federatedtesting/otel/postgres/get_all_postgres_metrics",
    json={},  # or {"commit_sha": "specific-sha"}
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)

metrics = response.json()
```

## What Metrics Are Available?

The PostgreSQL receiver metadata includes **~40 metrics** such as:

**Enabled by default:**
- `postgresql.backends` - Number of backends
- `postgresql.db_size` - Database disk usage
- `postgresql.commits` - Number of commits
- `postgresql.rollbacks` - Number of rollbacks
- `postgresql.operations` - DB row operations
- `postgresql.blocks_read` - Number of blocks read
- `postgresql.rows` - Number of rows in database
- `postgresql.index.scans` - Index scans on tables
- `postgresql.table.size` - Disk space used by tables
- And many more...

**Disabled by default (but available):**
- `postgresql.deadlocks`
- `postgresql.sequential_scans`
- `postgresql.temp_files`
- `postgresql.database.locks`
- And more...

## Data Source

Fetches from:
```
https://raw.githubusercontent.com/open-telemetry/opentelemetry-collector-contrib/
270e3cb8cdfe619322be1af2b49a0901d8188a9c/
receiver/postgresqlreceiver/metadata.yaml
```

You can override the commit SHA in any tool call to fetch from a different version.

## Troubleshooting

### Import Error

If you get an import error when running the service:

```python
# Change this in main.py:
from .otel_metadata_fetcher import OTelMetadataFetcher

# To this if needed:
from otel_metadata_fetcher import OTelMetadataFetcher
```

### Network Issues

The fetcher uses `httpx` with a 30-second timeout. If GitHub is slow or unreachable, increase the timeout:

```python
fetcher = OTelMetadataFetcher()
fetcher.client = httpx.Client(timeout=60.0)  # 60 seconds
```

### Cache

The fetcher uses `@lru_cache` to cache results. To clear the cache:

```python
from otel_metadata_fetcher import OTelMetadataFetcher
OTelMetadataFetcher.fetch_postgres_metadata.cache_clear()
```

## Next Steps

1. ✅ Install dependencies: `pip install -r requirements.txt`
2. ✅ Run example: `python example_usage.py`
3. ✅ Run tests: `pytest test_otel_fetcher.py -v`
4. ✅ Start service: `python main.py`
5. ✅ Test MCP tools from your client (Cursor, CLI, etc.)

## Support

For questions about this tool or system-tests, ask in [#apm-shared-testing](https://dd.enterprise.slack.com/archives/CHANNEL_ID).

---

**Note:** This is a standalone utility tool in system-tests. It can be used for development, testing, or as a reference implementation.

