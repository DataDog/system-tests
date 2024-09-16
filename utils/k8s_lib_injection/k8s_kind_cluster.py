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

        kind_command = f"kind create cluster --image=kindest/node:v1.25.3@sha256:f52781bc0d7a19fb6c405c2af83abfeb311f130707a0e219175677e366cc45d1 --name {k8s_kind_cluster.cluster_name} --config {cluster_config} --wait 1m"

        if "GITLAB_CI" in os.environ:
            # Kind needs to run in bridge network to communicate with the internet: https://github.com/DataDog/buildenv/blob/master/cookbooks/dd_firewall/templates/rules.erb#L96
            new_env = os.environ.copy()
            new_env["KIND_EXPERIMENTAL_DOCKER_NETWORK"] = "bridge"
            execute_command(kind_command, subprocess_env=new_env)

            setup_kind_in_gitlab(k8s_kind_cluster)
        else:
            execute_command(kind_command)

    return k8s_kind_cluster


def destroy_cluster(k8s_kind_cluster):
    execute_command(f"kind delete cluster --name {k8s_kind_cluster.cluster_name}")
    execute_command(f"docker rm -f {k8s_kind_cluster.cluster_name}-control-plane")


def setup_kind_in_gitlab(k8s_kind_cluster):
    # The build runs in a docker container:
    #    - Docker commands are forwarded to the host.
    #    - The kind container is a sibling to the build container
    # Three things need to happen
    # 1) The kind container needs to be in the bridge network to communicate with the internet: one in _ensure_cluster()
    # 2) Kube config needs to be altered to use the correct IP of the control plane server
    # 3) The internal port needs to be used: handled in get_agent_port() and get_weblog_port()
    execute_command(f"docker container inspect {k8s_kind_cluster.cluster_name}-control-plane --format '{{{{json .}}}}'")
    control_plane_ip = execute_command(f"docker container inspect {k8s_kind_cluster.cluster_name}-control-plane --format '{{{{.NetworkSettings.Networks.bridge.IPAddress}}}}'")

    container_info = execute_command("docker container ls --format '{{json .}}'")
    control_plane_server = ""

    # for item in container_info.decode().split("\n"):
    for item in container_info.split("\n"):
        if not item:
            continue
        container = json.loads(item)
        if container["Names"] == f"{k8s_kind_cluster.cluster_name}-control-plane":
            # Ports is of the form: "127.0.0.1:44371->6443/tcp",
            all_ports = container["Ports"].split(",")
            for port in all_ports:
                if "->6443/tcp" in port:
                    control_plane_server = port.replace("->6443/tcp", "").strip()
            logger.debug(f"[setup_kind_in_gitlab] control_plane_server: {control_plane_server}")

    if not control_plane_server:
        raise Exception("Unable to find control plane server")

    # Replace server config with dns name + internal port
    execute_command_sync(
        f"sed -i -e \"s/{control_plane_server}/{control_plane_ip}:6443/g\" {os.environ['HOME']}/.kube/config",
        k8s_kind_cluster,
    )

    execute_command_sync(f"cat {os.environ['HOME']}/.kube/config", k8s_kind_cluster)

    k8s_kind_cluster.cluster_host_name = control_plane_ip


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


    def get_agent_port(self):
        if self.docker_in_docker:
            return self.internal_agent_port
        return self.agent_port

    def get_weblog_port(self):
        if self.docker_in_docker:
            return self.internal_weblog_port
        return self.weblog_port
