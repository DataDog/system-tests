# Getting Container ID on Docker Desktop for macOS

## Problem

When running system-tests on Docker Desktop for macOS, the weblog container reads `/proc/self/cgroup` and gets:
```
0::/
```

This results in `weblog_container_id = None` because the cgroup path is just `/` (root) instead of containing a container ID pattern like `/docker/<container_id>`.

## Root Cause

Docker Desktop on macOS:
1. Runs containers inside a LinuxKit VM
2. Uses **private cgroup namespaces** by default (Docker's `cgroupns=private` mode)
3. In private mode, containers see themselves at the root of their own cgroup namespace (`/`)

## Solution Implemented

I've added support for configuring the **cgroup namespace mode** for containers:

### Changes Made

1. **Added `cgroupns_mode` parameter** to `TestedContainer` class (`utils/_context/containers.py`)
2. **Set `cgroupns_mode="host"` for weblog** in the DEFAULT scenario (`utils/_context/_scenarios/default.py`)

### How It Works

Setting `cgroupns_mode="host"` makes the container use the **host's cgroup namespace** instead of a private one. This means:
- The container can see the full cgroup hierarchy
- `/proc/self/cgroup` will show the actual path like `0::/docker/<container_id>`
- Container ID extraction works correctly

### Code Changes

```python
# In utils/_context/_scenarios/default.py
def configure(self, config: pytest.Config):
    super().configure(config)
    library = self.weblog_container.image.labels["system-tests-library"]
    value = _iast_security_controls_map[library]
    self.weblog_container.environment["DD_IAST_SECURITY_CONTROLS_CONFIGURATION"] = value

    # Set cgroupns to host mode to ensure container ID is visible in /proc/self/cgroup
    # This is particularly important for Docker Desktop on macOS where the default
    # private cgroup namespace shows "/" as the cgroup path
    self.weblog_container.cgroupns_mode = "host"
```

## Testing

Run the test again:
```bash
TEST_LIBRARY=golang ./run.sh DEFAULT -k test_data_integrity -v
```

Check the logs for:
```
cgroup: file content is ['0::/docker/<64-char-hex-id>', '']
cgroup: weblog container id is <64-char-hex-id>
```

## Alternative Solutions

If you need different approaches for different scenarios:

### 1. Environment Variable Injection

Instead of reading from cgroups, inject the container ID as an environment variable:

```python
# In scenario configure method
container_id = self.weblog_container._container.id
self.weblog_container.environment["DD_CONTAINER_ID"] = container_id
```

Then modify the tracer to read from `DD_CONTAINER_ID` if available.

### 2. Mount Docker Socket (Not Recommended)

Mount `/var/run/docker.sock` to let the container query the Docker API:

```python
self.weblog_container.volumes["/var/run/docker.sock"] = {
    "bind": "/var/run/docker.sock",
    "mode": "ro"
}
```

**Warning**: This is a security risk and not recommended for production-like testing.

### 3. Scenario-Specific Configuration

Apply `cgroupns_mode="host"` only to specific scenarios:

```python
# In any scenario's configure method
if sys.platform == "darwin":  # macOS only
    self.weblog_container.cgroupns_mode = "host"
```

### 4. Docker Compose Alternative

If using Docker Compose, add to `docker-compose.yml`:

```yaml
services:
  weblog:
    cgroupns: host
```

## Impact & Considerations

### Security
- `cgroupns=host` gives the container visibility into the host's cgroup hierarchy
- This is acceptable for testing environments
- **Not recommended for production** (but system-tests is a testing framework)

### Compatibility
- Works on Docker Desktop (macOS, Windows)
- Works on Linux (already had container IDs, but this ensures consistency)
- Requires Docker Engine 20.10+ (released Dec 2020)

### Test Behavior
- The test `test_trace_header_container_tags` will now properly validate the `Datadog-Container-ID` header
- Previously, it was skipping validation when `weblog_container_id` was `None`

## Docker Cgroup Namespace Modes

For reference, Docker supports three cgroup namespace modes:

1. **`private`** (default): Container sees itself at cgroup root (`/`)
2. **`host`**: Container sees the host's cgroup hierarchy (includes container ID)
3. **`shareable`**: Allows sharing cgroup namespace with other containers

## References

- Docker cgroup namespace docs: https://docs.docker.com/engine/reference/run/#cgroup-namespace-mode
- Docker Python SDK: https://docker-py.readthedocs.io/en/stable/containers.html
- System-tests cgroup parsing: `utils/cgroup_info.py`

## Rollback

If you need to revert this change:

```bash
git checkout utils/_context/containers.py utils/_context/_scenarios/default.py
```

Or simply remove the line:
```python
self.weblog_container.cgroupns_mode = "host"
```

