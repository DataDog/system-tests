import os

import uvicorn


uvicorn.run(
    "apm_test_client.server:app", host="0.0.0.0", port=int(os.getenv("APM_TEST_CLIENT_SERVER_PORT")), log_level="debug"
)
