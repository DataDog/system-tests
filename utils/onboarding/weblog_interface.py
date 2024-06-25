import time
from random import randint
import os
import requests


def make_get_request(app_url):
    generated_uuid = str(randint(1, 100000000000000000))
    requests.get(
        app_url,
        headers={
            "x-datadog-trace-id": generated_uuid,
            "x-datadog-parent-id": generated_uuid,
            "x-datadog-sampling-priority": "2",
        },
        timeout=10,
    )
    return generated_uuid


def warmup_weblog(app_url):
    for _ in range(15):
        try:
            requests.get(app_url, timeout=10)
            break
        except Exception:
            time.sleep(5)


def make_internal_get_request(stdin_file, vm_port):
    """This method is exclusively for testing through KrunVm microVM.
    It is used to make a request to the weblog application inside the VM, using stdin file"""

    generated_uuid = str(randint(1, 100000000000000000))
    timeout = 80
    script_to_run = f"""#!/bin/bash
echo "Requesting weblog..." 
URL="http://localhost:{vm_port}/"
TIMEOUT={timeout}
TRACE_ID={generated_uuid}
PARENT_ID={generated_uuid}
ps
while true; do
  RESPONSE=$(curl -i -m 2 -H "x-datadog-trace-id: $TRACE_ID" -H "x-datadog-parent-id: $PARENT_ID" -H "x-datadog-sampling-priority: 2" $URL)
  echo "$RESPONSE"
  if [[ $(echo "$RESPONSE" | grep "HTTP/1.1 200 OK") ]]; then
    echo "HTTP status 200 received: OK"
    break
  fi

  if [[ $SECONDS -ge $TIMEOUT ]]; then
    echo "Status 200 not received in $TIMEOUT seconds"
    break
  fi
  sleep 1
done"""
    script_name = "request_weblog.sh"
    shared_folder = os.path.dirname(os.path.abspath(stdin_file))

    # Write the script in the shared folder
    with open(os.path.join(shared_folder, script_name), "w", encoding="utf-8") as file:
        file.write(script_to_run)

    # Write the command to run the script in the stdin file
    with open(stdin_file, "a", encoding="utf-8") as file:
        file.write(f"chmod 755 /shared_volume/{script_name} \n")
        file.write(f"bash /shared_volume/{script_name} \n")

    # Wait for the script to finish
    start = time.time()
    while os.stat(stdin_file).st_size != 0 and time.time() - start < (timeout + 5):
        time.sleep(1)
    if os.stat(stdin_file).st_size != 0:
        raise TimeoutError("Timed out waiting for weblog ready")

    return generated_uuid
