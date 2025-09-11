# Node.js Sample App - Docker SSI Testing

## Overview
This sample application is designed for Docker SSI (Single Step Instrumentation) testing with locked Node.js runtime and npm dependencies.

## Dependency Locking Features

### ✅ Runtime Version Locking
- **Script**: `utils/build/ssi/base/js_install_runtimes.sh`
- **NVM Version**: v0.40.1 (locked)
- **npm Version**: 10.2.4 (locked)
- **Node.js Version**: Exact X.Y.Z format required (e.g., 18.19.0)

### ✅ Package Dependencies Locking
- **package.json**: Defines exact dependency versions
- **package-lock.json**: Locks complete dependency tree
- **.npmrc**: Controls npm behavior for reproducible builds

## Supported Node.js Versions

Based on system-tests configuration, these are the main versions tested:

### Production Versions
```bash
# Node.js 20 (Current LTS) - Most common in new scenarios
./utils/build/ssi/base/js_install_runtimes.sh 20.11.1

# Node.js 18 (LTS) - Most widely used in system-tests  
./utils/build/ssi/base/js_install_runtimes.sh 18.19.1

# Node.js 16 (Legacy LTS) - For backward compatibility
./utils/build/ssi/base/js_install_runtimes.sh 16.20.2
```

### Testing Versions
```bash
# Node.js 8 (Unsupported) - For negative testing
./utils/build/ssi/base/js_install_runtimes.sh 8.17.0

# Node.js 12 (Legacy) - For Docker SSI scenarios
./utils/build/ssi/base/js_install_runtimes.sh 12.0
```

## npm Version Compatibility Matrix

The script automatically selects compatible npm versions based on Node.js version:

| Node.js Version | npm Version | Compatibility |
|-----------------|-------------|---------------|
| 20+ | 10.2.4 | Latest npm for modern Node.js |
| 18.x | 9.9.3 | Compatible with Node.js 18 LTS |
| 16.x | 8.19.4 | Compatible with Node.js 16 LTS |
| 14.x | 6.14.18 | Legacy npm for Node.js 14 |
| 12.x | 6.14.18 | Legacy npm for Node.js 12 |
| 10.x | 6.14.18 | Legacy npm for Node.js 10 |
| 8.x | 6.14.15 | Legacy npm for Node.js 8 |

**Note**: The script automatically detects Node.js version and installs the most compatible npm version, preventing compatibility errors.

## Testing the Script

### ✅ Test Version Validation
```bash
# Valid format - should work
./utils/build/ssi/base/js_install_runtimes.sh 18.19.1

# Invalid formats - should fail with error
./utils/build/ssi/base/js_install_runtimes.sh 18.19      # Missing patch
./utils/build/ssi/base/js_install_runtimes.sh 18         # Missing minor.patch  
./utils/build/ssi/base/js_install_runtimes.sh latest     # Non-numeric
./utils/build/ssi/base/js_install_runtimes.sh            # Missing argument
```

### ✅ Test Exact Version Installation
```bash
# Check that exact version gets installed (not latest patch)
./utils/build/ssi/base/js_install_runtimes.sh 18.19.0
node --version  # Should output: v18.19.0 (exact match)
```

### ✅ Test Reproducible Builds
```bash
# Build container multiple times - should be identical
./utils/build/build.sh --library nodejs --weblog-variant js-app
docker images | grep js-app  # Check image sizes are consistent
```

## Sample App Endpoints

### Basic Endpoints
- `GET /` - "Hello, world!"
- `GET /info` - Dependency information and versions

### Testing Endpoints
- `GET /crashme` - Process crash simulation
- `GET /fork_and_crash` - Child process crash testing
- `GET /child_pids` - Process management testing
- `GET /zombies` - Zombie process detection

### Example Response (`/info`)
```json
{
  "pid": 1,
  "uptime": 5.234,
  "nodeVersion": "v18.19.1",
  "dependencies": {
    "lodash": "4.17.21",
    "moment": "2.29.4",
    "uuid": "available"
  },
  "sampleArray": [3, 1, 5, 2, 4],
  "timestamp": "2024-01-15 10:30:45",
  "requestId": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

## Build Process

### Docker Layer Caching

#### **Docker SSI Build (`utils/build/ssi/nodejs/js-app.Dockerfile`)**
```dockerfile
# package*.json copied first for optimal caching
COPY lib-injection/build/docker/nodejs/sample-app/package*.json ./
COPY lib-injection/build/docker/nodejs/sample-app/.npmrc ./

# npm ci ensures reproducible installs
RUN npm ci --only=production --no-audit --no-fund
```

#### **End-to-End Testing Build (`lib-injection/build/docker/nodejs/sample-app/Dockerfile`)**
```dockerfile
# Copy package files first for better Docker layer caching
COPY package*.json ./
COPY .npmrc ./

# Install dependencies with exact versions using npm ci
RUN npm ci --only=production --no-audit --no-fund
```

**Note**: Both Dockerfiles now use the same dependency locking approach for consistency.

## Testing the Builds

### **Build and Test Docker SSI:**
```bash
# Build the Docker SSI app
./utils/build/build.sh --library nodejs --weblog-variant js-app

# Test dependency injection endpoints
curl http://localhost:18080/info
# Returns JSON with dependency versions and usage examples
```

### **Build and Test End-to-End Docker:**
```bash
# Navigate to sample app directory
cd lib-injection/build/docker/nodejs/sample-app

# Build the Docker image
docker build -t nodejs-sample-app .

# Run the container
docker run -p 18080:18080 nodejs-sample-app

# Test the app endpoints
curl http://localhost:18080/        # Hello, world!
curl http://localhost:18080/info    # Dependency information
```

### **Verify Locked Dependencies:**
```bash
# Dependencies will be exactly the same versions every time
npm ci --only=production

# Check installed versions match package-lock.json
npm list --depth=0
```

### Version Verification
The runtime installation script includes multiple verification steps:
1. **Input validation**: X.Y.Z format required
2. **Installation verification**: Exact version match check
3. **Final verification**: Runtime version confirmation
4. **Error handling**: Clear error messages for mismatches

## Dependencies

### Production Dependencies
- **express**: 4.18.2 - Web framework (backwards compatible)
- **lodash**: 4.17.21 - Utility library
- **moment**: 2.29.4 - Date manipulation
- **uuid**: 8.3.2 - UUID generation
- **debug**: 4.3.4 - Debugging utility

### Development Dependencies  
- **eslint**: 7.32.0 - Code linting

### Node.js Compatibility
- **Minimum**: Node.js 8.0.0
- **Tested**: Node.js 8, 16, 18, 20
- **Recommended**: Node.js 18+ for best performance

## Troubleshooting

### Version Mismatch Errors
```bash
Error: Node.js version must be in exact format X.Y.Z
```
**Solution**: Use exact semantic versioning (e.g., 18.19.1, not 18.19 or 18)

### NVM Installation Failures
```bash
Error: NVM installation failed
```
**Solution**: Check network connectivity and NVM version availability

### Version Verification Failures
```bash
Error: Final Node.js version verification failed!
```
**Solution**: The requested Node.js version may not be available in NVM registry

## Best Practices

1. **Always use exact versions**: X.Y.Z format for reproducible builds
2. **Test multiple versions**: Verify compatibility across Node.js 16, 18, 20
3. **Use npm ci**: Not npm install for production builds  
4. **Check Docker layer caching**: Optimize Dockerfile for faster builds
5. **Verify installation**: Always check final versions match expectations

---

This setup ensures **100% reproducible builds** across all environments! 🚀
