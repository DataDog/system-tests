import os
import sys

import uvicorn


if len(sys.argv) > 1:
    framework = sys.argv[1]
else:
    raise ValueError("Framework is required")

uvicorn.run(
    f"integration_frameworks.{framework}:app",
    host="0.0.0.0",
    port=int(os.getenv("FRAMEWORK_TEST_CLIENT_SERVER_PORT", "80")),
    log_level="debug",
)
