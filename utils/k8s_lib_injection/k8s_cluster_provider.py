import os
import subprocess
import tempfile
import json
import base64
import time
import yaml
from pathlib import Path
from utils._logger import logger
from utils.k8s_lib_injection.k8s_command_utils import execute_command
from kubernetes import client, config


class PrivateRegistryConfig:
    """Configuration for private Docker registry access"""

    # Cache environment variables as class attributes
    _private_docker_registry = os.getenv("PRIVATE_DOCKER_REGISTRY", "")
    _private_docker_registry_user = os.getenv("PRIVATE_DOCKER_REGISTRY_USER", "")
    _private_registry_token = os.getenv("PRIVATE_DOCKER_REGISTRY_TOKEN", "")

    @classmethod
    def get_private_docker_registry(cls) -> str:
        """Get the private Docker registry URL"""
        return cls._private_docker_registry

    @classmethod
    def get_private_docker_registry_user(cls) -> str:
        """Get the private Docker registry user"""
        return cls._private_docker_registry_user

    @classmethod
    def get_private_registry_token(cls) -> str:
        """Get the private registry token"""
        return cls._private_registry_token

    @classmethod
    def is_configured(cls) -> bool:
        """Check if all required fields are configured"""
        return bool(cls._private_docker_registry and cls._private_docker_registry_user and cls._private_registry_token)


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

    def configure(self):
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
        if PrivateRegistryConfig.is_configured():
            execute_command(
                'kubectl patch serviceaccount spark -p \'{"imagePullSecrets": [{"name": "private-registry-secret"}]}\''
            )

    def _create_secret_to_access_to_internal_registry(self):
        # Create a kubernetes secret to access to the internal registry
        logger.info("Creating ECR secret")
        if not PrivateRegistryConfig.is_configured():
            logger.info("Skipping creation of ECR secret because private registry configuration is not complete")
            return
        try:
            # Create a temporary file with the docker config
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
                docker_config = {
                    "auths": {
                        PrivateRegistryConfig.get_private_docker_registry(): {
                            "auth": base64.b64encode(
                                f"{PrivateRegistryConfig.get_private_docker_registry_user()}:{PrivateRegistryConfig.get_private_registry_token()}".encode()
                            ).decode()
                        }
                    }
                }
                json.dump(docker_config, temp_file)
                temp_file.flush()
                temp_file_path = temp_file.name

            try:
                # Create the secret using the config file
                execute_command(
                    f"kubectl create secret generic private-registry-secret "
                    f"--from-file=.dockerconfigjson={temp_file_path} "
                    f"--type=kubernetes.io/dockerconfigjson",
                    quiet=True,
                )
                logger.info("Successfully created ECR secret")

                # Patch the default service account to use the secret
                execute_command(
                    'kubectl patch serviceaccount default -p \'{"imagePullSecrets": [{"name": "private-registry-secret"}]}\''
                )
                logger.info("Successfully patched default service account")
            finally:
                # Clean up the temporary file
                Path(temp_file_path).unlink()
        except Exception as e:
            logger.error(f"Error creating ECR secret: {e!s}")
            raise


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

        # Wait for the cluster to be ready
        time.sleep(10)
        logs = execute_command("kubectl get serviceaccounts ", logfile="serviceaccounts.log")
        logger.info(f"Service accounts logs: {logs}")
        # Method to create a kubernetes secret to access to the internal registry
        if PrivateRegistryConfig.is_configured():
            self._create_secret_to_access_to_internal_registry()

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
        # In CI environments, use dedicated CI config for Docker-in-Docker compatibility
        if "CI" in os.environ:
            cluster_template = "utils/k8s_lib_injection/resources/kind-config-ci-template.yaml"
        else:
            cluster_template = "utils/k8s_lib_injection/resources/kind-config-template.yaml"

        self._cluster_info = K8sClusterInfo(
            cluster_name="lib-injection-testing",
            context_name="kind-lib-injection-testing",
            cluster_template=cluster_template,
        )


    def _fix_kubeconfig_for_ci(self):
        """Fix kubeconfig server address for Docker-in-Docker CI environments"""
        try:
            kubeconfig_path = os.path.expanduser("~/.kube/config")
            logger.info(f"[CI Fix] Fixing kubeconfig server address in {kubeconfig_path}")

            # Read current kubeconfig
            with open(kubeconfig_path, 'r') as f:
                kubeconfig_content = f.read()

            logger.info(f"[CI Fix] Original kubeconfig content:\n{kubeconfig_content}")
            print(f"[CI Fix] Original kubeconfig server URLs:")
            import re
            server_lines = [line for line in kubeconfig_content.split('\n') if 'server:' in line]
            for line in server_lines:
                print(f"[CI Fix] Found: {line.strip()}")

            # Save original kubeconfig for debugging
            try:
                with open("original-kubeconfig.yaml", 'w') as f:
                    f.write(kubeconfig_content)
                logger.info("[CI Fix] Original kubeconfig saved to original-kubeconfig.yaml")
            except Exception as e:
                logger.warning(f"[CI Fix] Failed to save original kubeconfig: {e}")

            # Replace localhost, 0.0.0.0, and Docker internal IPs with docker in server URLs
            import re
            # Match various server URL patterns that need fixing in Docker-in-Docker CI
            patterns_to_fix = [
                # https://localhost:port -> https://docker:port
                (r'(\s+server:\s+https://)localhost(:[\d]+)', r'\1docker\2'),
                # https://0.0.0.0:port -> https://docker:port
                (r'(\s+server:\s+https://)0\.0\.0\.0(:[\d]+)', r'\1docker\2'),
                # https://172.17.0.x:port -> https://docker:port (Docker internal network)
                (r'(\s+server:\s+https://)172\.17\.0\.\d+(:[\d]+)', r'\1docker\2'),
                # https://172.18.0.x:port -> https://docker:port (kind network range)
                (r'(\s+server:\s+https://)172\.18\.0\.\d+(:[\d]+)', r'\1docker\2'),
            ]

            fixed_content = kubeconfig_content
            for pattern, replacement in patterns_to_fix:
                old_fixed = fixed_content
                fixed_content = re.sub(pattern, replacement, fixed_content)
                if old_fixed != fixed_content:
                    print(f"[CI Fix] Applied pattern: {pattern} -> {replacement}")

            if fixed_content == kubeconfig_content:
                print("[CI Fix] WARNING: No server URLs were modified!")

            # Write back the fixed kubeconfig
            with open(kubeconfig_path, 'w') as f:
                f.write(fixed_content)

            logger.info(f"[CI Fix] Fixed kubeconfig content:\n{fixed_content}")
            print(f"[CI Fix] Fixed kubeconfig server URLs:")
            fixed_server_lines = [line for line in fixed_content.split('\n') if 'server:' in line]
            for line in fixed_server_lines:
                print(f"[CI Fix] Fixed: {line.strip()}")

            # Save fixed kubeconfig for debugging
            try:
                with open("fixed-kubeconfig.yaml", 'w') as f:
                    f.write(fixed_content)
                logger.info("[CI Fix] Fixed kubeconfig saved to fixed-kubeconfig.yaml")
            except Exception as e:
                logger.warning(f"[CI Fix] Failed to save fixed kubeconfig: {e}")

            # Verify the fix worked
            try:
                test_output = execute_command("kubectl cluster-info")
                logger.info(f"[CI Fix] Verification - kubectl cluster-info: {test_output}")
            except Exception as e:
                logger.warning(f"[CI Fix] Verification failed: {e}")

        except Exception as e:
            logger.error(f"[CI Fix] Failed to fix kubeconfig: {e}")

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
        print("[DEBUG] K8sKindClusterProvider.ensure_cluster() method started")
        kind_command = f"kind create cluster --image=kindest/node:v1.25.3@sha256:f52781bc0d7a19fb6c405c2af83abfeb311f130707a0e219175677e366cc45d1 --name {self.get_cluster_info().cluster_name} --config {self.get_cluster_info().cluster_template} --wait 1m"

        logger.info(f"[Kind Create] Running command: {kind_command}")
        logger.info(f"[Kind Create] Using config file: {self.get_cluster_info().cluster_template}")

        # Show the config file content for debugging
        try:
            with open(self.get_cluster_info().cluster_template, 'r') as f:
                config_content = f.read()
            logger.info(f"[Kind Create] Config file content:\n{config_content}")
        except Exception as e:
            logger.warning(f"[Kind Create] Could not read config file: {e}")

        try:
            output = execute_command(kind_command)
            logger.info(f"[Kind Create] Command output: {output}")
            print(f"[Kind Create] SUCCESS: kind create command completed")
        except Exception as e:
            logger.error(f"[Kind Create] FAILED: kind create command failed: {e}")
            print(f"[Kind Create] FAILED: kind create command failed: {e}")
            # Still continue to reach the sleep for debugging
            pass

        # Check kubeconfig immediately after kind create
        print(f"[Kind Create] Checking kubeconfig after cluster creation...")
        try:
            kubeconfig_path = os.path.expanduser("~/.kube/config")
            print(f"[Kind Create] Kubeconfig path: {kubeconfig_path}")
            print(f"[Kind Create] Kubeconfig exists: {os.path.exists(kubeconfig_path)}")
            if os.path.exists(kubeconfig_path):
                with open(kubeconfig_path, 'r') as f:
                    content = f.read()
                print(f"[Kind Create] Kubeconfig size: {len(content)} bytes")
                print(f"[Kind Create] Kubeconfig preview: {content[:200]}...")
            else:
                print("[Kind Create] Kubeconfig file does not exist!")
        except Exception as e:
            print(f"[Kind Create] Failed to check kubeconfig: {e}")

        # Try to manually get kubeconfig from kind
        try:
            print(f"[Kind Create] Getting kubeconfig directly from kind...")
            kind_kubeconfig = execute_command(f"kind get kubeconfig --name {cluster_name}")
            print(f"[Kind Create] Kind kubeconfig output: {kind_kubeconfig[:200]}...")

            # Write it to the standard location
            kubeconfig_dir = os.path.expanduser("~/.kube")
            os.makedirs(kubeconfig_dir, exist_ok=True)
            with open(os.path.join(kubeconfig_dir, "config"), 'w') as f:
                f.write(kind_kubeconfig)
            print("[Kind Create] Wrote kubeconfig to ~/.kube/config")
        except Exception as e:
            print(f"[Kind Create] Failed to get kubeconfig from kind: {e}")

        # Verify cluster accessibility immediately after creation
        cluster_name = self.get_cluster_info().cluster_name
        context_name = self.get_cluster_info().context_name

        logger.info("[Kind Create] Verifying cluster accessibility...")
        try:
            # Test with kind- prefixed context
            kind_context_output = execute_command(f"kubectl cluster-info --context kind-{cluster_name}")
            logger.info(f"[Kind Create] Cluster info (kind-{cluster_name}): {kind_context_output}")
        except Exception as e:
            logger.warning(f"[Kind Create] Failed to get cluster info with kind-{cluster_name}: {e}")

        try:
            # Test with configured context name
            context_output = execute_command(f"kubectl cluster-info --context {context_name}")
            logger.info(f"[Kind Create] Cluster info ({context_name}): {context_output}")
        except Exception as e:
            logger.warning(f"[Kind Create] Failed to get cluster info with {context_name}: {e}")

        try:
            # Test with default context (should be set by kind create)
            default_output = execute_command("kubectl cluster-info")
            logger.info(f"[Kind Create] Cluster info (default context): {default_output}")
        except Exception as e:
            logger.warning(f"[Kind Create] Failed to get cluster info with default context: {e}")

        # Apply CI-specific kubeconfig fixes
        if "CI" in os.environ:
            try:
                logger.info("[Kind Create] Applying CI-specific kubeconfig fixes...")
                print("[Kind Create] Applying CI-specific kubeconfig fixes...")
                self._fix_kubeconfig_for_ci()
                print("[Kind Create] SUCCESS: CI kubeconfig fixes completed")
            except Exception as e:
                logger.error(f"[Kind Create] FAILED: CI kubeconfig fixes failed: {e}")
                print(f"[Kind Create] FAILED: CI kubeconfig fixes failed: {e}")
                # Continue to reach the sleep for debugging

        # Apply GitLab-specific setup if in GitLab CI
        if "GITLAB_CI" in os.environ:
            try:
                logger.info("[Kind Create] Applying GitLab-specific setup...")
                print("[Kind Create] Applying GitLab-specific setup...")
                self._setup_kind_in_gitlab()
                print("[Kind Create] SUCCESS: GitLab setup completed")
            except Exception as e:
                logger.error(f"[Kind Create] FAILED: GitLab setup failed: {e}")
                print(f"[Kind Create] FAILED: GitLab setup failed: {e}")
                # Continue to reach the sleep for debugging

        # Wait for cluster to be fully ready
        logger.info("[Kind Create] Waiting for cluster to stabilize...")
        logger.info("[DEBUG SLEEP] Starting 20-minute debug sleep - connect to the pod for manual debugging")
        print("[DEBUG SLEEP] Starting 20-minute debug sleep - connect to the pod for manual debugging")

        # Create debug marker file in tmp
        try:
            import tempfile
            debug_file = os.path.join(tempfile.gettempdir(), "kind-debug-sleep-active")
            with open(debug_file, 'w') as f:
                f.write("Kind cluster debug sleep started at: " + str(time.time()) + "\n")
                f.write("Cluster name: " + self.get_cluster_info().cluster_name + "\n")
                f.write("Context name: " + self.get_cluster_info().context_name + "\n")
            logger.info(f"[DEBUG SLEEP] Created debug marker file: {debug_file}")
            print(f"[DEBUG SLEEP] Created debug marker file: {debug_file}")
        except Exception as e:
            logger.warning(f"[DEBUG SLEEP] Failed to create debug marker file: {e}")

        time.sleep(1200)  # 20 minutes for extended debugging

        # Remove debug marker file
        try:
            if os.path.exists(debug_file):
                os.remove(debug_file)
            logger.info("[DEBUG SLEEP] Debug sleep completed, marker file removed")
            print("[DEBUG SLEEP] Debug sleep completed, marker file removed")
        except Exception as e:
            logger.warning(f"[DEBUG SLEEP] Failed to remove debug marker file: {e}")
        # Method to create a kubernetes secret to access to the internal registry
        if PrivateRegistryConfig.is_configured():
            self._create_secret_to_access_to_internal_registry()

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
