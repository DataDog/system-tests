import time
from random import randint
import requests
from utils.tools import logger


def make_get_request(app_url):
    generated_uuid = str(randint(0, 10000000))
    requests.get(
        app_url, headers={"x-datadog-trace-id": generated_uuid, "x-datadog-parent-id": generated_uuid}, timeout=10
    )
    return generated_uuid


def warmup_weblog(app_url):
    for _ in range(3):
        try:
            requests.get(app_url, timeout=10)
            break
        except Exception as e:
            logger.debug(f"Error warming up weblog: {e}")
            time.sleep(5)
