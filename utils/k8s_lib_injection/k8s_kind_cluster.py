import time
import os
import socket
import random
import tempfile
from uuid import uuid4

from utils.k8s_lib_injection.k8s_command_utils import execute_command
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
    k8s_kind_cluster.confiure_ports()

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

        if "GITLAB_CI" in os.environ:
            # The build runs in a docker container. Docker commands are forwarded to the host. The kind container is a sibling to the build container
            # The build container needs to be added to the kind network for them to be able to communicate

            # the name of the container endswith "build"
            build_container_id = execute_command(f"docker container ls --format '{{json .}}' | jq --slurp '.[] | select(.Names | endswith(\"-build\")) | .ID' --raw-output")

            if not build_container_id:
                raise Exception("Unable to find build container ID")

            execute_command(f"docker network connect kind {build_container_id}")
            execute_command("sed -i -E \"s@server:.+@server:\ https://lib-injection-testing-control-plane:6443@g\" $HOME/.kube/config")

            k8s_kind_cluster.build_container_id = build_container_id

        # time.sleep(20)

    return k8s_kind_cluster


def destroy_cluster(k8s_kind_cluster):
    execute_command(f"kind delete cluster --name {k8s_kind_cluster.cluster_name}")
    execute_command(f"docker rm -f {k8s_kind_cluster.cluster_name}-control-plane")

    # remove the docker container from the kind network. See the Gitlab comments above
    if k8s_kind_cluster.build_container_id:
        execute_command(f"docker network disconnect kind {k8s_kind_cluster.build_container_id} || true")

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
        self.agent_port = 18126
        self.weblog_port = 18080

    def confiure_ports(self):
        # Get random free ports
        self.agent_port = get_free_port()
        self.weblog_port = get_free_port()
