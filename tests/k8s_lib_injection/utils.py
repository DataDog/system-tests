import time

import requests
from kubernetes import client

from utils import logger, context
from utils.k8s_lib_injection.k8s_cluster_provider import K8sClusterInfo
from utils._context._scenarios.k8s_lib_injection import K8sScenario, K8sScenarioWithClusterProvider


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


def get_cluster_info() -> K8sClusterInfo:
    assert isinstance(context.scenario, K8sScenarioWithClusterProvider)

    return context.scenario.k8s_cluster_provider.get_cluster_info()


def get_library_init_image() -> str:
    """Return the init image under test (the image the scenario deploys as the init container)."""
    assert isinstance(context.scenario, K8sScenario)

    return context.scenario.test_weblog.library_init_image


def run_https_probe_pod(
    k8s_cluster_info: K8sClusterInfo, image: str, url: str, *, namespace: str = "default", timeout: int = 120
) -> tuple[str | None, str]:
    """Run a one-shot pod from `image` performing a TLS-verified HTTPS GET to `url`.

    Uses the image's curl with verification on (no -k), so a missing or invalid CA trust
    store makes curl exit non-zero. Returns (pod_phase, logs); phase "Succeeded" means the
    image completed a verified HTTPS request. The probe pod is always cleaned up.
    """
    api = k8s_cluster_info.core_v1_api()
    name = "init-https-probe"
    pod = client.V1Pod(
        metadata=client.V1ObjectMeta(name=name),
        spec=client.V1PodSpec(
            restart_policy="Never",
            containers=[
                client.V1Container(
                    name="probe",
                    image=image,
                    image_pull_policy="Always",
                    command=["/usr/bin/curl", "-fsS", "-o", "/dev/null", "--max-time", "15", url],
                )
            ],
        ),
    )
    logger.info(f"[HTTPS probe] running {image} -> curl {url}")
    api.create_namespaced_pod(namespace=namespace, body=pod)
    try:
        phase: str | None = None
        deadline = time.time() + timeout
        while time.time() < deadline:
            phase = api.read_namespaced_pod_status(name=name, namespace=namespace).status.phase
            if phase in ("Succeeded", "Failed"):
                break
            time.sleep(2)
        logs = ""
        try:
            logs = api.read_namespaced_pod_log(name=name, namespace=namespace)
        except Exception as e:
            logger.warning(f"[HTTPS probe] could not read probe pod logs: {e}")
        return phase, logs
    finally:
        try:
            api.delete_namespaced_pod(name=name, namespace=namespace)
        except Exception as e:
            logger.warning(f"[HTTPS probe] could not delete probe pod: {e}")
