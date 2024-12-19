import os
from utils.tools import logger
from utils.k8s_lib_injection.k8s_command_utils import execute_command
from kubernetes import client, config


class K8sClusterProvider:
    """Common interface for all the providers that will be used to create the k8s cluster."""

    def __init__(self, is_local_managed=False):
        self.is_local_managed = is_local_managed
        self._cluster_info = None

    def configure(self):
        pass

    def get_cluster_info(self):
        """It should return a K8sClusterInfo object with the cluster information"""
        if self._cluster_info is None:
            raise ValueError("Cluster not configured")
        return self._cluster_info

    def ensure_cluster(self):
        """All local managed clusters should be created here"""
        if self.is_local_managed:
            raise NotImplementedError
        logger.info("Using an external K8s cluster")

    def destroy_cluster(self):
        if self.is_local_managed:
            raise NotImplementedError
        logger.info("Using an external K8s cluster: Remember to clean up the resources!!")

    def create_spak_service_account(self):
        """Create service account for launching spark application in k8s"""
        execute_command(f"kubectl create serviceaccount spark")
        execute_command(
            f"kubectl create clusterrolebinding spark-role --clusterrole=edit --serviceaccount=default:spark --namespace=default"
        )


class K8sClusterInfo:
    def __init__(self, cluster_name=None, context_name=None, cluster_host_name="localhost", cluster_template=None):
        self.cluster_name = cluster_name
        self.context_name = context_name
        self.cluster_host_name = cluster_host_name
        self.agent_port = None
        self.weblog_port = None
        self.internal_agent_port = None
        self.internal_weblog_port = None
        self.docker_in_docker = False
        self.cluster_template = cluster_template
        self._kubeconfig_initialized = False

    def configure_networking(
        self,
        docker_in_docker=False,
        agent_port=8126,
        weblog_port=18080,
        internal_agent_port=8126,
        internal_weblog_port=18080,
    ):
        self.docker_in_docker = docker_in_docker
        self.agent_port = agent_port
        self.weblog_port = weblog_port
        self.internal_agent_port = internal_agent_port
        self.internal_weblog_port = internal_weblog_port

    def get_agent_port(self):
        if self.docker_in_docker:
            return self.internal_agent_port
        return self.agent_port

    def get_weblog_port(self):
        if self.docker_in_docker:
            return self.internal_weblog_port
        return self.weblog_port

    def _configure_kubeconfig(self):
        try:
            config.load_kube_config()
            logger.info(f"kube config loaded")
            self._kubeconfig_initialized = True
        except Exception as e:
            logger.error(f"Error loading kube config: {e}")
            raise e

    def core_v1_api(self):
        """Provides de CoreV1Api object (from kubernetes python api) to interact with the k8s cluster"""
        if not self._kubeconfig_initialized:
            self._configure_kubeconfig()
        return client.CoreV1Api(api_client=config.new_client_from_config(context=self.context_name))

    def apps_api(self):
        """Provides de AppsV1Api object (from kubernetes python api) to interact with the k8s cluster"""
        if not self._kubeconfig_initialized:
            self._configure_kubeconfig()
        return client.AppsV1Api(api_client=config.new_client_from_config(context=self.context_name))


class K8sMiniKubeClusterProvider(K8sClusterProvider):
    """Provider for kind k8s clusters"""

    def __init__(self):
        super().__init__(is_local_managed=True)

    def configure(self):
        self._cluster_info = K8sClusterInfo(cluster_name="minikube", context_name="minikube")
        self._cluster_info.configure_networking(docker_in_docker="GITLAB_CI" in os.environ)

    def ensure_cluster(self):
        logger.info("Ensuring MiniKube cluster")
        execute_command("minikube start --extra-config=apiserver.service-node-port-range=8100-18081")
        execute_command("minikube status")
        # Set the cluster host name/minikube ip. We need to start the cluster first
        self._cluster_info.cluster_host_name = execute_command("minikube ip").strip()
        logger.info(f"Cluster host name: {self._cluster_info.cluster_host_name}")

    def destroy_cluster(self):
        logger.info("Destroying MiniKube cluster")
        execute_command("minikube delete")


class K8sKindClusterProvider(K8sClusterProvider):
    """Provider for kind k8s clusters"""

    def __init__(self):
        super().__init__(is_local_managed=True)

    def configure(self):
        self._cluster_info = K8sClusterInfo(
            cluster_name="lib-injection-testing",
            context_name="kind-lib-injection-testing",
            cluster_template="utils/k8s_lib_injection/resources/kind-config-template.yaml",
        )
        self._cluster_info.configure_networking(docker_in_docker="GITLAB_CI" in os.environ)

    def ensure_cluster(self):
        logger.info("Ensuring kind cluster")
        kind_command = f"kind create cluster --image=kindest/node:v1.25.3@sha256:f52781bc0d7a19fb6c405c2af83abfeb311f130707a0e219175677e366cc45d1 --name {self.get_cluster_info().cluster_name} --config {self.get_cluster_info().cluster_template} --wait 1m"

        if "GITLAB_CI" in os.environ:
            # Kind needs to run in bridge network to communicate with the internet: https://github.com/DataDog/buildenv/blob/master/cookbooks/dd_firewall/templates/rules.erb#L96
            new_env = os.environ.copy()
            new_env["KIND_EXPERIMENTAL_DOCKER_NETWORK"] = "bridge"
            execute_command(kind_command, subprocess_env=new_env)

            self._setup_kind_in_gitlab()
        else:
            execute_command(kind_command)

    def destroy_cluster(self):
        logger.info("Destroying kind cluster")
        execute_command(f"kind delete cluster --name {self.get_cluster_info().cluster_name}")
        execute_command(f"docker rm -f {self.get_cluster_info().cluster_name}-control-plane")

    def _setup_kind_in_gitlab(self):
        # The build runs in a docker container:
        #    - Docker commands are forwarded to the host.
        #    - The kind container is a sibling to the build container
        # Three things need to happen
        # 1) The kind container needs to be in the bridge network to communicate with the internet: done in _ensure_cluster()
        # 2) Kube config needs to be altered to use the correct IP of the control plane server
        # 3) The internal ports needs to be used rather than external ports: handled in get_agent_port() and get_weblog_port()
        correct_control_plane_ip = execute_command(
            f"docker container inspect {self.get_cluster_info().cluster_name}-control-plane --format '{{{{.NetworkSettings.Networks.bridge.IPAddress}}}}'"
        ).strip()
        if not correct_control_plane_ip:
            raise Exception("Unable to find correct control plane IP")
        logger.debug(f"[setup_kind_in_gitlab] correct_control_plane_ip: {correct_control_plane_ip}")

        control_plane_address_in_config = execute_command(
            f'docker container inspect {self.get_cluster_info().cluster_name}-control-plane --format \'{{{{index .NetworkSettings.Ports "6443/tcp" 0 "HostIp"}}}}:{{{{index .NetworkSettings.Ports "6443/tcp" 0 "HostPort"}}}}\''
        ).strip()
        if not control_plane_address_in_config:
            raise Exception("Unable to find control plane address from config")
        logger.debug(f"[setup_kind_in_gitlab] control_plane_address_in_config: {control_plane_address_in_config}")

        # Replace server config with dns name + internal port
        execute_command(
            f"sed -i -e 's/{control_plane_address_in_config}/{correct_control_plane_ip}:6443/g' {os.environ['HOME']}/.kube/config"
        )

        self.get_cluster_info().cluster_host_name = correct_control_plane_ip
