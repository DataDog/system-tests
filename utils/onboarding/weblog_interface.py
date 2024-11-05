import time
from random import randint
import os
import json
from typing import List
import requests
from utils.onboarding.wait_for_tcp_port import wait_for_port
from utils.tools import logger


def make_get_request(app_url, swallow: bool = False) -> str:
    generated_uuid = str(randint(1, 100000000000000000))
    try:
        requests.get(
            app_url,
            headers={
                "x-datadog-trace-id": generated_uuid,
                "x-datadog-parent-id": generated_uuid,
                "x-datadog-sampling-priority": "2",
            },
            timeout=15,
        )
    except Exception as e:
        if not swallow:
            raise
        logger.warning(e)
    return generated_uuid


def warmup_weblog(app_url):
    for _ in range(15):
        try:
            r = requests.get(app_url, timeout=10)
            if r.status_code == 200:
                if "application/json" in r.headers["content-type"]:
                    json_text = r.text.replace("'", '"')
                    json_res = json.loads(json_text)
                    logger.info(f"Weblog response: {json_res}")
                    if "app_type" in json_res and json_res["app_type"] == "multicontainer":
                        return json_res
                    logger.info(f"Weblog is not multicontainer, response: {json_res}")
                break
            time.sleep(2)
        except Exception:
            time.sleep(5)
    return None


def make_internal_get_request(stdin_file, vm_port):
    """ This method is exclusively for testing through KrunVm microVM.
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


def request_weblog(virtual_machine, vm_ip, vm_port) -> List[str]:
    request_uuids = []
    if virtual_machine.krunvm_config is not None and virtual_machine.krunvm_config.stdin is not None:
        logger.info(
            "We are testing on krunvm. The request to the weblog will be done using the stdin (inside the microvm)"
        )
        request_uuids = [make_internal_get_request(virtual_machine.krunvm_config.stdin, vm_port)]
    else:
        logger.info(f"Waiting for weblog available [{vm_ip}:{vm_port}]")
        wait_for_port(vm_port, vm_ip, 80.0)
        logger.info(f"[{vm_ip}]: Weblog app is ready!")
        responseJson = warmup_weblog(f"http://{vm_ip}:{vm_port}/")
        if responseJson is not None:
            logger.info(f"There is a multicontainer app: {responseJson}")
            for app in responseJson["apps"]:
                warmup_weblog(f"http://{vm_ip}:{vm_port}{app['url']}")
                logger.info(f"Making a request to weblog [http://{vm_ip}:{vm_port}{app['url']}]")
                request_uuids.append(make_get_request(f"http://{vm_ip}:{vm_port}{app['url']}"))
                time.sleep(1)
        else:
            logger.info(f"Making a request to weblog [{vm_ip}:{vm_port}]")
            request_uuids.append(make_get_request(f"http://{vm_ip}:{vm_port}/"))

    return request_uuids
