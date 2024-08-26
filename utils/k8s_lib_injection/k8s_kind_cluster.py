import json
import time
import os
import socket
import random
import tempfile
from uuid import uuid4

from utils.k8s_lib_injection.k8s_command_utils import execute_command, execute_command_sync
from utils.tools import logger
from utils import context


def ensure_cluster():
    try:
        return _ensure_cluster()
    except Exception as e:
        # It's difficult, but sometimes the cluster is not created correctly, releated to the ports conflicts
        logger.error(f"Error ensuring cluster: {e}. trying again.")
        return _ensure_cluster()


def _ensure_cluster():
    k8s_kind_cluster = K8sKindCluster()
    k8s_kind_cluster.configure_networking(docker_in_docker="GITLAB_CI" in os.environ)

    kind_data = ""
    with open("utils/k8s_lib_injection/resources/kind-config-template.yaml", "r") as file:
        kind_data = file.read()

    kind_data = kind_data.replace("$$AGENT_PORT$$", str(k8s_kind_cluster.agent_port))
    kind_data = kind_data.replace("$$WEBLOG_PORT$$", str(k8s_kind_cluster.weblog_port))

    cluster_config = f"{context.scenario.host_log_folder}/{k8s_kind_cluster.cluster_name}_kind-config.yaml"

    with open(cluster_config, "w") as fp:
        fp.write(kind_data)
        fp.seek(0)
        execute_command(
            f"kind create cluster --image=kindest/node:v1.25.3@sha256:f52781bc0d7a19fb6c405c2af83abfeb311f130707a0e219175677e366cc45d1 --name {k8s_kind_cluster.cluster_name} --config {cluster_config} --wait 1m"
        )
        execute_command(
            f"kind load docker-image ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:latest --name {k8s_kind_cluster.cluster_name}"
        )
        execute_command(
            f"kind load docker-image gcr.io/datadoghq/cluster-agent:7.56.0 --name {k8s_kind_cluster.cluster_name}"
        )
        execute_command(
            f"kind load docker-image {os.getenv('LIBRARY_INJECTION_TEST_APP_IMAGE')} --name {k8s_kind_cluster.cluster_name}"
        )
        execute_command(f"kind load docker-image {os.getenv('LIB_INIT_IMAGE')} --name {k8s_kind_cluster.cluster_name}")

        if "GITLAB_CI" in os.environ:
            setup_kind_in_gitlab(k8s_kind_cluster)

        # time.sleep(20)

    return k8s_kind_cluster


def destroy_cluster(k8s_kind_cluster):
    execute_command(f"kind delete cluster --name {k8s_kind_cluster.cluster_name}")
    execute_command(f"docker rm -f {k8s_kind_cluster.cluster_name}-control-plane")


def setup_kind_in_gitlab(k8s_kind_cluster):
    # The build runs in a docker container:
    #    - Docker commands are forwarded to the host.
    #    - The kind container is a sibling to the build container
    # Two things need to happen
    # 1) The build container needs to be added to the kind network for them to be able to communicate
    # 2) Kube config needs to be altered to use the dns name of the control plane server

    container_info = execute_command("docker container ls --format '{{json .}}'")

    build_container_id = ""
    control_plane_server = ""
    control_plane_server_container_id = ""

    for item in container_info.decode().split("\n"):
        if not item:
            continue
        container = json.loads(item)
        if container["Names"].endswith("-build") or "libdatadog-build" in container["Image"]:
            build_container_id = container["ID"]
        if container["Names"] == f"{k8s_kind_cluster.cluster_name}-control-plane":
            control_plane_server_container_id = container["ID"]
            # Ports is of the form: "127.0.0.1:44371->6443/tcp",
            logger.debug(f"[setup_kind_in_gitlab] Container ports: {container['Ports']}")
            all_ports = container["Ports"].split(",")
            for port in all_ports:
                if "->6443/tcp" in port:
                    control_plane_server = port.replace("->6443/tcp", "").strip()
            logger.debug(f"[setup_kind_in_gitlab] control_plane_server: {control_plane_server}")

    if not build_container_id:
        raise Exception("Unable to find build container ID")
    if not control_plane_server:
        raise Exception("Unable to find control plane server")

    # Add build container to kind network
    try:
        execute_command(f"docker network connect kind {build_container_id}")
        logger.debug(f"[setup_kind_in_gitlab] Connected build container to kind network")
    except Exception as e:
        logger.debug(f"[setup_kind_in_gitlab] Ignoring error connecting build container to kind network: {e}")

    # Connect control_plane_server to the bridget network. Access to internet
    # execute_command(f"docker network connect bridge {control_plane_server_container_id}")

    # Replace server config with dns name + internal port
    execute_command_sync(
        f"sed -i -e \"s/{control_plane_server}/{k8s_kind_cluster.cluster_name}-control-plane:6443/g\" {os.environ['HOME']}/.kube/config",
        k8s_kind_cluster,
    )

    execute_command_sync(f"cat {os.environ['HOME']}/.kube/config", k8s_kind_cluster)
    k8s_kind_cluster.build_container_id = build_container_id


def get_free_port():
    last_allowed_port = 65535
    port = random.randint(1100, 65100)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while port <= last_allowed_port:
        try:
            sock.bind(("", port))
            sock.close()
            return port
        except OSError:
            port += 1
    raise IOError("no free ports")


class K8sKindCluster:
    def __init__(self):
        self.cluster_name = f"lib-injection-testing-{str(uuid4())[:8]}"
        self.context_name = f"kind-{self.cluster_name}"
        self.cluster_host_name = "localhost"
        self.agent_port = None
        self.weblog_port = None
        self.internal_agent_port = None
        self.internal_weblog_port = None
        self.docker_in_docker = False

    def configure_networking(self, docker_in_docker=False):
        self.docker_in_docker = docker_in_docker
        self.agent_port = get_free_port()
        self.weblog_port = get_free_port()
        self.internal_agent_port = 8126
        self.internal_weblog_port = 18080
        if docker_in_docker:
            self.cluster_host_name = f"{self.cluster_name}-control-plane"

    def get_agent_port(self):
        if self.docker_in_docker:
            return self.internal_agent_port
        return self.agent_port

    def get_weblog_port(self):
        if self.docker_in_docker:
            return self.internal_weblog_port
        return self.weblog_port
