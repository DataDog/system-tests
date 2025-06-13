import os
import subprocess
from utils._logger import logger
from utils.k8s_lib_injection.k8s_command_utils import execute_command
from kubernetes import client, config


class K8sProviderFactory:
    """Use the correct provider specified by Id"""

    def get_provider(self, provider_id):
        logger.info(f"Using {provider_id} provider")
        if provider_id == "kind":
            return K8sKindClusterProvider()
        elif provider_id == "minikube":
            return K8sMiniKubeClusterProvider()
        elif provider_id == "eksremote":
            return K8sEKSRemoteClusterProvider()
        else:
            raise ValueError("Not supported provided", provider_id)


class K8sClusterProvider:
    """Common interface for all the providers that will be used to create the k8s cluster."""

    def __init__(self, is_local_managed=False):
        self.is_local_managed = is_local_managed
        self._cluster_info = None
        self._ecr_token = None

    def configure(self, ecr_token):
        self._ecr_token = ecr_token
        self.configure_cluster()
        self.configure_networking()
        # self.configure_cluster_api_connection()

    def configure_cluster(self):
        """Configure the cluster properties"""
        raise NotImplementedError

    def get_cluster_info(self):
        """It should return a K8sClusterInfo object with the cluster information"""
        if self._cluster_info is None:
            raise ValueError("Cluster not configured")
        return self._cluster_info

    def configure_networking(self):
        """Configure the networking properties for the cluster"""

        if self._cluster_info is None:
            raise ValueError("Cluster not configured")

        self._cluster_info.docker_in_docker = "GITLAB_CI" in os.environ
        self._cluster_info.agent_port = 8126
        self._cluster_info.weblog_port = 18080
        self._cluster_info.internal_agent_port = 8126
        self._cluster_info.internal_weblog_port = 18080
        self._cluster_info.cluster_host_name = "localhost"

    def configure_cluster_api_connection(self):
        """Configure the k8s cluster api connection"""
        try:
            config.load_kube_config()
        except Exception as e:
            logger.error(f"Error loading kube config: {e}")
            raise e

    def ensure_cluster(self):
        """All local managed clusters should be created here"""
        if self.is_local_managed:
            raise NotImplementedError
        logger.info(
            "Using an external K8s cluster. It should be already running. We are configuring the connection to it."
        )
        self.configure_cluster_api_connection()

    def destroy_cluster(self):
        # TODO RMM review sleep mode failures on get cluter logs
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
    def __init__(self, cluster_name=None, context_name=None, cluster_template=None):
        self.cluster_name = cluster_name
        self.context_name = context_name
        self.cluster_host_name = None
        self.agent_port = None
        self.weblog_port = None
        self.internal_agent_port = None
        self.internal_weblog_port = None
        self.docker_in_docker = False
        self.cluster_template = cluster_template

    def get_agent_port(self):
        if self.docker_in_docker:
            return self.internal_agent_port
        return self.agent_port

    def get_weblog_port(self):
        if self.docker_in_docker:
            return self.internal_weblog_port
        return self.weblog_port

    def core_v1_api(self):
        """Provides de CoreV1Api object (from kubernetes python api) to interact with the k8s cluster"""
        # return client.CoreV1Api(api_client=config.new_client_from_config(context=self.context_name))
        return client.CoreV1Api()

    def apps_api(self):
        """Provides de AppsV1Api object (from kubernetes python api) to interact with the k8s cluster"""
        # return client.AppsV1Api(api_client=config.new_client_from_config(context=self.context_name))
        return client.AppsV1Api()


class K8sMiniKubeClusterProvider(K8sClusterProvider):
    """Provider for Minikube k8s clusters"""

    def __init__(self):
        super().__init__(is_local_managed=True)

    def configure_cluster(self):
        self._cluster_info = K8sClusterInfo(cluster_name="minikube", context_name="minikube")

    def ensure_cluster(self):
        logger.info("Ensuring MiniKube cluster")
        execute_command("minikube start --driver docker --ports 18080:18080 --ports 8126:8126")
        execute_command("minikube status")
        # We need to configure the api after create the cluster
        self.configure_cluster_api_connection()

    def destroy_cluster(self):
        logger.info("Destroying MiniKube cluster")
        execute_command("minikube delete")


class K8sEKSRemoteClusterProvider(K8sClusterProvider):
    """Provider for remote EKS k8s clusters. The remote cluster should be already running
    and the kubeconfig should be available in the environment and the context should be set
    Remember to execute the scenario using aws-vault
    https://datadoghq.atlassian.net/wiki/spaces/TS/pages/2295038121/Creating+EKS+Cluster+Sandboxes
    """

    def __init__(self):
        super().__init__(is_local_managed=False)

    def configure_cluster(self):
        self._cluster_info = K8sClusterInfo(
            cluster_name="montero2Sandbox.us-east-1.eksctl.io",
            context_name="roberto.montero@datadoghq.com@montero2Sandbox.us-east-1.eksctl.io",
        )

    def configure_networking(self):
        """Configure the networking properties for the cluster"""

        if self._cluster_info is None:
            raise ValueError("Cluster not configured")

        self._cluster_info.docker_in_docker = "GITLAB_CI" in os.environ
        self._cluster_info.agent_port = 8126
        self._cluster_info.weblog_port = 18080
        self._cluster_info.internal_agent_port = 8126
        self._cluster_info.internal_weblog_port = 18080
        self._cluster_info.cluster_host_name = None

    def configure_cluster_api_connection(self):
        """Configure the k8s cluster api connection"""
        try:
            # Update context name
            # Current context name is like: "arn:aws:eks:us-east-1:601427279990:cluster/lib-injection-testing-eks-sandbox"
            # I only take "lib-injection-testing-eks-sandbox"
            arn, cluster_context = execute_command("kubectl config current-context").split("/")
            current_context_name = cluster_context.strip()

            ##weird: There is other context like: user@email.com@lib-injection-testing-eks-sandbox.us-east-1.eksctl.io
            self._cluster_info.context_name = self.execute_piped_command(
                "kubectl config get-contexts |  awk '{if ($1 ~ \"@" + current_context_name + "\") print $1}'"
            )
            logger.info("Configuring k8s cluster api connection, for context: " + self._cluster_info.context_name)

            # Update cluster name. Like: "lib-injection-testing-eks-sandbox.us-east-1.eksctl.io"
            self._cluster_info.cluster_name = execute_command(
                "kubectl config view -o jsonpath=\"{.contexts[?(@.name=='"
                + self._cluster_info.context_name
                + "')].context.cluster}\""
            ).strip()
            logger.info("Configuring k8s cluster api connection, for cluster: " + self._cluster_info.cluster_name)

            # We need to external IP to access to the test agent and the weblog (You should open manually the ports 8126 and 18080 in the aws security group before)
            self._cluster_info.cluster_host_name = execute_command(
                "kubectl get nodes --output jsonpath=\"{.items[0].status.addresses[?(@.type=='ExternalIP')].address}\""
            )
            logger.info(
                "Configuring k8s cluster api connection, for cluster host name: " + self._cluster_info.cluster_host_name
            )

            token = self.get_token(self._cluster_info.cluster_name)

            configuration = client.Configuration()

            # Set Cluster endpoint
            cluster_server_endpoint = execute_command(
                'kubectl config view --minify --output jsonpath="{.clusters[*].cluster.server}"'
            )
            logger.info(f"Cluster server endpoint: {cluster_server_endpoint}")

            configuration.host = cluster_server_endpoint
            configuration.verify_ssl = False
            configuration.debug = False  # Set true if you need more info (related with connection to the k8s cluster)
            configuration.api_key["authorization"] = "Bearer " + token
            configuration.assert_hostname = True
            configuration.verify_ssl = False
            client.Configuration.set_default(configuration)
            logger.info(f"kube config loaded")

        except Exception as e:
            logger.error(f"Error loading kube config: {e}")
            raise e

    def execute_piped_command(self, command):
        # awk_comm = 'kubectl config get-contexts |  awk \'{if ($1 ~ "@lib-injection-testing-eks-sandbox") print $1}\''
        p2 = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)  # noqa: S602
        res, err = p2.communicate()
        return res.decode("utf-8").strip()

    def get_token(self, cluster_name):
        # From cluster name like: "lib-injection-testing-eks-sandbox.us-east-1.eksctl.io" I only take "lib-injection-testing-eks-sandbox"
        cluster_min_name = cluster_name.split(".")[0]
        token = execute_command(f"aws-iam-authenticator token -i {cluster_min_name} --token-only")
        return token.strip()


class K8sKindClusterProvider(K8sClusterProvider):
    """Provider for kind k8s clusters"""

    def __init__(self):
        super().__init__(is_local_managed=True)

    def configure_cluster(self):
        self._cluster_info = K8sClusterInfo(
            cluster_name="lib-injection-testing",
            context_name="kind-lib-injection-testing",
            cluster_template="utils/k8s_lib_injection/resources/kind-config-template.yaml",
        )

    def configure_networking(self):
        """Configure the networking properties for the cluster"""

        if self._cluster_info is None:
            raise ValueError("Cluster not configured")

        self._cluster_info.docker_in_docker = "GITLAB_CI" in os.environ
        self._cluster_info.agent_port = 8127
        self._cluster_info.weblog_port = 18081
        self._cluster_info.internal_agent_port = 8126
        self._cluster_info.internal_weblog_port = 18080
        self._cluster_info.cluster_host_name = "localhost"

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
        # Method to create a kubernetes secret to access to the internal registry
        if self._ecr_token:
            self._create_secret_to_access_to_internal_registry(self._ecr_token)
        
        # We need to configure the api after create the cluster
        self.configure_cluster_api_connection()

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

    def _create_secret_to_access_to_internal_registry(self, ecr_token):
        # Create a kubernetes secret to access to the internal registry
        logger.info("Creating ECR secret")
        try:
            # Create the secret
            execute_command(
                f"kubectl create secret docker-registry ecr-secret "
                f"--docker-server=235494822917.dkr.ecr.us-east-1.amazonaws.com "
                f"--docker-username=AWS "
                f"--docker-password={ecr_token}"
            )
            logger.info("Successfully created ECR secret")
            
            # Patch the default service account to use the secret
            execute_command(
                'kubectl patch serviceaccount default -p \'{"imagePullSecrets": [{"name": "ecr-secret"}]}\''
            )
            logger.info("Successfully patched default service account")
        except Exception as e:
            logger.error(f"Error creating ECR secret: {str(e)}")
            raise
        