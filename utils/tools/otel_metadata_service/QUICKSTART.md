# 🚀 Quick Start - Standalone FastAPI Service

This is a **standalone FastAPI service** that fetches OpenTelemetry PostgreSQL receiver metadata from GitHub. No Rapid dependencies required!

## ⚡ 30-Second Start

```bash
# 1. Navigate to the service directory
cd /Users/quinna.halim/system-tests/utils/tools/otel_metadata_service

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the service
python main.py

# 4. Open your browser
# Visit: http://localhost:8080/docs
```

That's it! 🎉

## 📋 What You Get

### Interactive API Documentation
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

### REST API Endpoints

| Endpoint | Description | Example |
|----------|-------------|---------|
| `GET /` | Service info | `curl http://localhost:8080/` |
| `GET /health` | Health check | `curl http://localhost:8080/health` |
| `GET /api/v1/metrics` | All metrics | `curl http://localhost:8080/api/v1/metrics` |
| `GET /api/v1/metrics/enabled` | Enabled metrics only | `curl http://localhost:8080/api/v1/metrics/enabled` |
| `GET /api/v1/metrics/{name}` | Specific metric | `curl http://localhost:8080/api/v1/metrics/postgresql.backends` |
| `GET /api/v1/resource-attributes` | Resource attributes | `curl http://localhost:8080/api/v1/resource-attributes` |
| `GET /api/v1/attributes` | Attributes | `curl http://localhost:8080/api/v1/attributes` |
| `GET /api/v1/events` | Events | `curl http://localhost:8080/api/v1/events` |
| `GET /api/v1/metadata/full` | Complete metadata | `curl http://localhost:8080/api/v1/metadata/full` |

## 🎯 Quick Examples

### Example 1: Get All Metrics
```bash
curl http://localhost:8080/api/v1/metrics | jq
```

### Example 2: Get Only Enabled Metrics
```bash
curl http://localhost:8080/api/v1/metrics/enabled | jq
```

### Example 3: Get Specific Metric
```bash
curl http://localhost:8080/api/v1/metrics/postgresql.backends | jq
```

### Example 4: Use Custom Commit SHA
```bash
curl "http://localhost:8080/api/v1/metrics?commit_sha=270e3cb8cdfe619322be1af2b49a0901d8188a9c" | jq
```

### Example 5: Get Events
```bash
curl http://localhost:8080/api/v1/events | jq
```

## 🐍 Python Client Example

```python
import httpx

# Create client
client = httpx.Client(base_url="http://localhost:8080")

# Get all metrics
response = client.get("/api/v1/metrics")
metrics = response.json()
print(f"Found {len(metrics)} metrics")

# Get a specific metric
response = client.get("/api/v1/metrics/postgresql.backends")
metric = response.json()
print(f"Metric: {metric['description']}")

# Get enabled metrics only
response = client.get("/api/v1/metrics/enabled")
enabled = response.json()
print(f"Enabled metrics: {len(enabled)}")
```

## 🔧 Advanced Usage

### Custom Port
```bash
python main.py 9000
# Service runs on http://localhost:9000
```

### Run in Background
```bash
nohup python main.py > service.log 2>&1 &
```

### Stop the Service
```bash
# Find the process
ps aux | grep "python main.py"

# Kill it
kill <PID>
```

## 🧪 Test the Service

### Run the Example Script
```bash
python example_usage.py
```

### Run the Test Suite
```bash
pytest test_otel_fetcher.py -v
```

### Manual Health Check
```bash
curl http://localhost:8080/health
# Response: {"status":"healthy"}
```

## 🌐 Access from Other Machines

The service binds to `0.0.0.0`, so it's accessible from other machines:

```bash
# From another machine on the same network
curl http://YOUR_MACHINE_IP:8080/health
```

## 📦 What's Included

```
federatedtesting/
├── main.py                    # FastAPI service (START HERE!)
├── otel_metadata_fetcher.py   # Core fetcher module
├── example_usage.py           # Standalone examples
├── test_otel_fetcher.py       # Test suite
├── requirements.txt           # Dependencies
├── QUICKSTART.md             # This file
├── README.md                 # Full documentation
└── SETUP.md                  # Detailed setup guide
```

## 🔍 Explore the API

Once running, visit **http://localhost:8080/docs** for:
- ✅ Interactive API playground
- ✅ Try out each endpoint
- ✅ See request/response schemas
- ✅ Test with different parameters

## 📊 Example Output

```json
{
  "postgresql.backends": {
    "enabled": true,
    "description": "The number of backends.",
    "unit": "1",
    "sum": {
      "value_type": "int",
      "monotonic": false,
      "aggregation_temporality": "cumulative"
    },
    "stability": {
      "level": "development"
    }
  }
}
```

## 🛠️ Troubleshooting

### Port Already in Use
```bash
# Use a different port
python main.py 8081
```

### Missing Dependencies
```bash
pip install -r requirements.txt
```

### Can't Fetch from GitHub
- Check your internet connection
- GitHub might be rate limiting (wait a few minutes)
- Try a different commit SHA

## 💡 Pro Tips

1. **Bookmark the docs**: http://localhost:8080/docs
2. **Use `jq` for pretty JSON**: `curl ... | jq`
3. **Check logs**: All errors appear in terminal
4. **Cache is enabled**: First request may be slow, subsequent requests are fast
5. **Test locally first**: Use `python example_usage.py` before starting the service

## 🎓 Next Steps

1. ✅ Run `python main.py`
2. ✅ Open http://localhost:8080/docs
3. ✅ Try the `/api/v1/metrics` endpoint
4. ✅ Explore other endpoints
5. ✅ Integrate with your application

## 📞 Support

- **Questions?** Ask in [#apm-shared-testing](https://dd.enterprise.slack.com/archives/CHANNEL_ID)
- **Issues?** Check the logs in your terminal
- **Want to contribute?** Update `main.py` and add more endpoints!

---

**Remember**: This is a standalone utility tool in system-tests. Use it for development, testing, or as a reference! 🏠

