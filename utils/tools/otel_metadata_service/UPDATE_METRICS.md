# Update PostgreSQL Metrics Workflow

Quick guide to fetch the latest PostgreSQL metrics and use them in system-tests.

## 🚀 Quick Start

### 1. Start the Service (if not running)

```bash
cd /Users/quinna.halim/system-tests/utils/tools/otel_metadata_service
python main.py
```

Keep this running in a terminal.

### 2. Update Metrics (in another terminal)

```bash
cd /Users/quinna.halim/system-tests/utils/tools/otel_metadata_service
python update_postgres_metrics.py
```

This will:
- ✅ Fetch metrics from `http://localhost:8080/api/v1/metrics/summary`
- ✅ Save to `postgres_metrics.json`
- ✅ Generate Python code in `postgres_metrics.py`
- ✅ Print the Python code to copy/paste

## 📋 Output Files

After running the script, you'll have:

1. **`postgres_metrics.json`** - Raw JSON data
   ```json
   {
     "postgresql.backends": {
       "data_type": "Sum",
       "description": "The number of backends."
     }
   }
   ```

2. **`postgres_metrics.py`** - Python module you can import
   ```python
   postgresql_metrics = {
       "postgresql.backends": {
           "data_type": "Sum",
           "description": "The number of backends."
       }
   }
   ```

## 💻 Using in Your Tests

### Option 1: Import from the generated file

```python
# In your test file
from utils.tools.otel_metadata_service.postgres_metrics import postgresql_metrics

# Now use it
assert "postgresql.backends" in postgresql_metrics
assert postgresql_metrics["postgresql.backends"]["data_type"] == "Sum"
```

### Option 2: Copy/paste the code

The script prints the Python code to your terminal. Just copy and paste it into your test file:

```python
# tests/otel_postgres_metrics_e2e/test_postgres_metrics.py

postgresql_metrics = {
    "postgresql.backends": {
        "data_type": "Sum",
        "description": "The number of backends."
    },
    # ... more metrics
}
```

## 🎯 Example Usage in Tests

```python
# tests/otel_postgres_metrics_e2e/test_postgres_metrics.py
from utils.tools.otel_metadata_service.postgres_metrics import postgresql_metrics

@scenarios.otel_collector_e2e
class Test_PostgresMetrics:
    def test_metrics_present(self):
        # Validate that all expected metrics are present
        for metric_name, metric_info in postgresql_metrics.items():
            # Check metric exists in collected data
            assert self.has_metric(metric_name)
            
            # Validate the data type
            expected_type = metric_info["data_type"]
            actual_type = self.get_metric_type(metric_name)
            assert actual_type == expected_type
```

## 🔄 Cursor Integration

With the `.cursorrules` file in the system-tests root, you can now ask Cursor:

> "Update the postgres metrics"

And Cursor will know to:
1. Check if the service is running
2. Run the update script
3. Show you the output

## 🛠️ Troubleshooting

### Service not running
```
❌ Error: Could not connect to the service.
   Make sure the service is running: python main.py
```

**Solution**: Start the service first:
```bash
cd utils/tools/otel_metadata_service
python main.py
```

### Wrong format
The output format matches the system-tests PR #5532:
- Metric names as keys (not in a list)
- Capitalized types: `"Sum"`, `"Gauge"`, not `"sum"`, `"gauge"`
- Fields: `data_type` and `description`

## 📊 Verifying the Output

Check that the format matches what you expect:

```bash
# View the JSON
cat postgres_metrics.json | jq

# Check a specific metric
cat postgres_metrics.json | jq '.["postgresql.backends"]'
# Should output:
# {
#   "data_type": "Sum",
#   "description": "The number of backends."
# }
```

## 🔗 Related Files

- Main service: `main.py`
- Update script: `update_postgres_metrics.py`
- Example usage: `example_usage.py`
- Tests using this: `tests/otel_postgres_metrics_e2e/test_postgres_metrics.py`
- Cursor rules: `.cursorrules` (in system-tests root)

## 💡 Pro Tips

1. **Always use latest**: The service defaults to the `main` branch, so you always get the latest metrics
2. **Version specific**: Add `?commit_sha=<sha>` to the URL if you need a specific version
3. **Keep it updated**: Re-run the script when OpenTelemetry releases new metrics
4. **Use in CI**: You can run this in CI to ensure tests match the latest metadata

---

**Questions?** Check the [README.md](README.md) or [QUICKSTART.md](QUICKSTART.md) in this directory.

