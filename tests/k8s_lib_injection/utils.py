import time

import requests
from utils import logger
from utils.k8s_lib_injection.k8s_cluster_provider import K8sClusterInfo


def get_dev_agent_traces(k8s_cluster_info: K8sClusterInfo, retry: int = 10) -> list:
    """get_dev_agent_traces fetches traces from the dev agent running in the k8s cluster."""
    dev_agent_url = f"http://{k8s_cluster_info.cluster_host_name}:{k8s_cluster_info.get_agent_port()}/test/traces"
    for _ in range(retry):
        logger.info(f"[Check traces] Checking traces : {dev_agent_url}")
        response = requests.get(dev_agent_url, timeout=60)
        traces_json = response.json()
        if len(traces_json) > 0:
            logger.debug(f"Test traces response: {traces_json}")
            return traces_json
        time.sleep(2)
    return []
