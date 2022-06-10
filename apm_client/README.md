"""

## M1 mac install:

```sh
/usr/bin/python3 -m virtualenv .venv
source .venv/bin/activate
arch -x86_64 pip install --upgrade pip
arch -x86_64 pip install -r requirements.txt
arch -x86_64 python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. protos/apm_test_client.proto
DEV_MODE=1 arch -x86_64 pytest test_client_stats.py
```
ref: https://github.com/grpc/grpc/issues/25082#issuecomment-754718296
"""
