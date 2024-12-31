import time

import requests
from utils.tools import logger


def get_dev_agent_traces(k8s_kind_cluster, retry=10):
    """get_dev_agent_traces fetches traces from the dev agent running in the k8s cluster."""
    for _ in range(retry):
        logger.info(f"[Check traces] Checking traces:")
        response = requests.get(
            f"http://{k8s_kind_cluster.cluster_host_name}:{k8s_kind_cluster.get_agent_port()}/test/traces"
        )
        traces_json = response.json()
        if len(traces_json) > 0:
            logger.debug(f"Test traces response: {traces_json}")
            return traces_json
        time.sleep(2)
    return []
