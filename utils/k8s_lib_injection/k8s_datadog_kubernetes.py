import os
import time
import yaml
from pathlib import Path
from kubernetes import client, watch
from utils._logger import logger
from utils.k8s_lib_injection.k8s_command_utils import (
    helm_add_repo,
    helm_install_chart,
    execute_command,
)
from utils.k8s_lib_injection.k8s_logger import k8s_logger
from retry import retry
from utils.k8s_lib_injection.k8s_cluster_provider import PrivateRegistryConfig


class K8sDatadog:
    def __init__(self, output_folder):
        self.output_folder = output_folder

    def configure(
        self,
        k8s_cluster_info,
        dd_cluster_feature={},
        dd_cluster_uds=None,
        dd_cluster_version=None,
        dd_cluster_img=None,
        api_key=None,
        app_key=None,
    ):
        self.k8s_cluster_info = k8s_cluster_info
        self.dd_cluster_feature = dd_cluster_feature
        self.dd_cluster_uds = dd_cluster_uds
        self.dd_cluster_version = dd_cluster_version
        self.dd_cluster_img = dd_cluster_img
        self.api_key = api_key
        self.app_key = app_key
        logger.info(f"K8sDatadog configured with cluster: {self.k8s_cluster_info.cluster_name}")

    def deploy_test_agent(self, namespace="default"):
        """Installs the test agent pod."""

        logger.info(f"[Test agent] Deploying Datadog test agent on the cluster: {self.k8s_cluster_info.cluster_name}")

        container = client.V1Container(
            name="trace-agent",
            image="ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:v1.31.1",
            image_pull_policy="Always",
            ports=[client.V1ContainerPort(container_port=8126, host_port=8126, name="traceport", protocol="TCP")],
            command=["ddapm-test-agent"],
            env=[
                client.V1EnvVar(name="SNAPSHOT_CI", value="0"),
                client.V1EnvVar(name="PORT", value="8126"),
                client.V1EnvVar(name="DD_APM_RECEIVER_SOCKET", value="/var/run/datadog/apm.socket"),
                client.V1EnvVar(name="LOG_LEVEL", value="DEBUG"),
                client.V1EnvVar(
                    name="ENABLED_CHECKS", value="trace_count_header,meta_tracer_version_header,trace_content_length"
                ),
            ],
            volume_mounts=[client.V1VolumeMount(mount_path="/var/run/datadog", name="datadog")],
            readiness_probe=client.V1Probe(
                initial_delay_seconds=10,  # Increased from 1s to 10s to allow dd-apm-test-agent to start
                period_seconds=2,
                timeout_seconds=10,
                success_threshold=1,
                failure_threshold=5,  # Added failure threshold for better debugging
                tcp_socket=client.V1TCPSocketAction(port=8126),
            ),
            liveness_probe=client.V1Probe(
                initial_delay_seconds=15,
                period_seconds=15,
                timeout_seconds=10,
                success_threshold=1,
                failure_threshold=12,
                tcp_socket=client.V1TCPSocketAction(port=8126),
            ),
        )
        # Template
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": "datadog"}),
            spec=client.V1PodSpec(
                containers=[container],
                dns_policy="ClusterFirst",
                node_selector={"kubernetes.io/os": "linux"},
                restart_policy="Always",
                scheduler_name="default-scheduler",
                security_context=client.V1PodSecurityContext(run_as_user=0),
                termination_grace_period_seconds=30,
                volumes=[
                    client.V1Volume(
                        name="datadog",
                        host_path=client.V1HostPathVolumeSource(path="/var/run/datadog", type="DirectoryOrCreate"),
                    )
                ],
            ),
        )
        # Spec
        spec = client.V1DaemonSetSpec(
            selector=client.V1LabelSelector(match_labels={"app": "datadog"}), template=template
        )
        # DaemonSet
        daemonset = client.V1DaemonSet(
            api_version="apps/v1", kind="DaemonSet", metadata=client.V1ObjectMeta(name="datadog"), spec=spec
        )
        self.k8s_cluster_info.apps_api().create_namespaced_daemon_set(namespace=namespace, body=daemonset)

        self.wait_for_test_agent(namespace)
        logger.info("[Test agent] Daemonset created")

    def deploy_datadog_cluster_agent(self, host_log_folder: str, namespace="default"):
        """Installs the Datadog Cluster Agent via helm for manual library injection testing.
        We enable the admission controller and wait for the datdog cluster to be ready.
        The Datadog Admission Controller is an important piece of the Datadog Cluster Agent.
        The main benefit of the Datadog Admission Controller is to simplify your life when it comes to configure your application Pods.
        Datadog Admission Controller is a Mutating Admission Controller type because it mutates, or changes, the pods configurations.
        """

        logger.info("[Deploy datadog cluster] Deploying Datadog Cluster Agent with Admission Controler")
        operator_file = "utils/k8s_lib_injection/resources/helm/datadog-helm-chart-values.yaml"
        if self.dd_cluster_uds:
            logger.info("[Deploy datadog cluster] Using UDS")
            operator_file = "utils/k8s_lib_injection/resources/helm/datadog-helm-chart-values-uds.yaml"

        logger.info("[Deploy datadog cluster] Configuring helm repository")
        helm_add_repo("datadog", "https://helm.datadoghq.com", self.k8s_cluster_info, update=True)

        logger.info(f"[Deploy datadog cluster]helm install datadog with config file [{operator_file}]")

        # Add the cluster agent tag version
        if self.dd_cluster_img is None:
            # DEPRECATED
            self.dd_cluster_feature["clusterAgent.image.tag"] = self.dd_cluster_version
        else:
            image_ref, tag = split_docker_image(self.dd_cluster_img)
            self.dd_cluster_feature["clusterAgent.image.tag"] = tag
            self.dd_cluster_feature["clusterAgent.image.repository"] = image_ref
            if PrivateRegistryConfig.is_configured():
                self.dd_cluster_feature["clusterAgent.image.pullSecrets[0].name"] = "private-registry-secret"

        helm_install_chart(
            host_log_folder,
            self.k8s_cluster_info,
            "datadog",
            "datadog/datadog",
            value_file=operator_file,
            set_dict=self.dd_cluster_feature,
        )

        logger.info("[Deploy datadog cluster] Waiting for the cluster to be ready")
        self._wait_for_cluster_agent_ready(namespace)

    def deploy_datadog_operator(self, host_log_folder: str, namespace="default"):
        """Datadog Operator is a Kubernetes Operator that enables you to deploy and configure the Datadog Agent in a Kubernetes environment.
        By using the Datadog Operator, you can use a single Custom Resource Definition (CRD) to deploy the node-based Agent,
        the Datadog Cluster Agent, and Cluster check runners.
        """
        logger.info("[Deploy datadog operator] Configuring helm repository")
        helm_add_repo("datadog", "https://helm.datadoghq.com", self.k8s_cluster_info, update=True)
        helm_install_chart(
            host_log_folder,
            self.k8s_cluster_info,
            "my-datadog-operator",
            "datadog/datadog-operator",
            value_file=None,
            set_dict={},
            timeout=None,
        )
        logger.info("[Deploy datadog operator] the operator is ready")
        logger.info("[Deploy datadog operator] Create the operator secrets")
        execute_command(
            f"kubectl create secret generic datadog-secret --from-literal api-key={self.api_key} --from-literal app-key={self.app_key}"
        )
        # Configure cluster agent image on the operator file
        if self.dd_cluster_img is None:
            # DEPRECATED
            oeprator_config_file = "utils/k8s_lib_injection/resources/operator/datadog-operator.yaml"
        else:
            oeprator_config_file = add_cluster_agent_img_operator_yaml(self.dd_cluster_img, self.output_folder)

        logger.info(f"[Deploy datadog operator] Create the operator custom resource from file {oeprator_config_file}")
        execute_command(f"kubectl apply -f {oeprator_config_file}")
        logger.info("[Deploy datadog operator] Waiting for the cluster to be ready")
        self._wait_for_cluster_agent_ready(namespace, label_selector="agent.datadoghq.com/component=cluster-agent")

    def wait_for_test_agent(self, namespace):
        """Waits for the test agent to be ready."""
        daemonset_created = False
        daemonset_status = None
        # Wait for the daemonset to be created
        for i in range(20):
            daemonset_status = self.k8s_cluster_info.apps_api().read_namespaced_daemon_set_status(
                name="datadog", namespace=namespace
            )
            if daemonset_status is not None and daemonset_status.status.number_ready > 0:
                logger.info(f"[Test agent] daemonset status datadog running!")
                daemonset_created = True
                break
            elif daemonset_status is None:
                logger.info(f"[Test agent] daemonset status datadog not found")
            time.sleep(5)

        if not daemonset_created:
            logger.info("[Test agent] Daemonset not created. Last status: %s" % daemonset_status)

            # Add extensive debugging before failing
            try:
                logger.info("[Test agent] DEBUG: Collecting daemonset debug information...")
                print("[Test agent] DEBUG: Collecting daemonset debug information...")

                # Check if daemonset exists
                try:
                    ds = self.k8s_cluster_info.apps_api().read_namespaced_daemon_set("datadog", namespace)
                    logger.info(f"[Test agent] DEBUG: DaemonSet exists - desired: {ds.status.desired_number_scheduled}, ready: {ds.status.number_ready}, available: {ds.status.number_available}")
                    print(f"[Test agent] DEBUG: DaemonSet exists - desired: {ds.status.desired_number_scheduled}, ready: {ds.status.number_ready}, available: {ds.status.number_available}")
                except Exception as e:
                    logger.info(f"[Test agent] DEBUG: DaemonSet not found: {e}")
                    print(f"[Test agent] DEBUG: DaemonSet not found: {e}")

                # Check pods
                try:
                    from kubernetes import client
                    v1 = client.CoreV1Api()
                    pods = v1.list_namespaced_pod(namespace, label_selector="app=datadog")
                    logger.info(f"[Test agent] DEBUG: Found {len(pods.items)} datadog pods")
                    print(f"[Test agent] DEBUG: Found {len(pods.items)} datadog pods")

                    for pod in pods.items:
                        pod_name = pod.metadata.name
                        logger.info(f"[Test agent] DEBUG: Pod {pod_name} - phase: {pod.status.phase}, ready: {pod.status.container_statuses[0].ready if pod.status.container_statuses else 'unknown'}")
                        print(f"[Test agent] DEBUG: Pod {pod_name} - phase: {pod.status.phase}, ready: {pod.status.container_statuses[0].ready if pod.status.container_statuses else 'unknown'}")

                        # Get pod logs using Kubernetes Python client
                        try:
                            logger.info(f"[Test agent] DEBUG: Getting logs from pod {pod_name}...")
                            print(f"[Test agent] DEBUG: Getting logs from pod {pod_name}...")
                            pod_logs = v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, tail_lines=50)
                            logger.info(f"[Test agent] DEBUG: Pod {pod_name} logs:\n{pod_logs}")
                            print(f"[Test agent] DEBUG: Pod {pod_name} logs:\n{pod_logs}")
                        except Exception as e:
                            logger.info(f"[Test agent] DEBUG: Failed to get logs from {pod_name}: {e}")
                            print(f"[Test agent] DEBUG: Failed to get logs from {pod_name}: {e}")

                        # Get pod description for more details
                        try:
                            logger.info(f"[Test agent] DEBUG: Getting detailed pod description for {pod_name}...")
                            print(f"[Test agent] DEBUG: Getting detailed pod description for {pod_name}...")
                            pod_details = v1.read_namespaced_pod(name=pod_name, namespace=namespace)

                            # Container status details
                            if pod_details.status.container_statuses:
                                for container_status in pod_details.status.container_statuses:
                                    logger.info(f"[Test agent] DEBUG: Container {container_status.name} - ready: {container_status.ready}, restart_count: {container_status.restart_count}")
                                    print(f"[Test agent] DEBUG: Container {container_status.name} - ready: {container_status.ready}, restart_count: {container_status.restart_count}")

                                    if container_status.state.waiting:
                                        logger.info(f"[Test agent] DEBUG: Container {container_status.name} waiting: {container_status.state.waiting.reason} - {container_status.state.waiting.message}")
                                        print(f"[Test agent] DEBUG: Container {container_status.name} waiting: {container_status.state.waiting.reason} - {container_status.state.waiting.message}")

                                    if container_status.state.terminated:
                                        logger.info(f"[Test agent] DEBUG: Container {container_status.name} terminated: exit_code={container_status.state.terminated.exit_code}, reason={container_status.state.terminated.reason}")
                                        print(f"[Test agent] DEBUG: Container {container_status.name} terminated: exit_code={container_status.state.terminated.exit_code}, reason={container_status.state.terminated.reason}")
                        except Exception as e:
                            logger.info(f"[Test agent] DEBUG: Failed to get pod details for {pod_name}: {e}")
                            print(f"[Test agent] DEBUG: Failed to get pod details for {pod_name}: {e}")

                        # In CI environment, add kubectl commands for manual debugging
                        if "CI" in __import__("os").environ:
                            logger.info(f"[Test agent] DEBUG: CI environment detected - use these commands for debugging:")
                            print(f"[Test agent] DEBUG: CI environment detected - use these commands for debugging:")
                            print(f"[Test agent] DEBUG: kubectl logs {pod_name} -n {namespace}")
                            print(f"[Test agent] DEBUG: kubectl exec -it {pod_name} -n {namespace} -- ps aux")
                            print(f"[Test agent] DEBUG: kubectl exec -it {pod_name} -n {namespace} -- netstat -tlnp")
                            print(f"[Test agent] DEBUG: kubectl exec -it {pod_name} -n {namespace} -- sh")

                        # Get pod events
                        try:
                            events = v1.list_namespaced_event(namespace, field_selector=f"involvedObject.name={pod_name}")
                            for event in events.items[-5:]:  # Last 5 events
                                logger.info(f"[Test agent] DEBUG: Pod {pod_name} event: {event.reason} - {event.message}")
                                print(f"[Test agent] DEBUG: Pod {pod_name} event: {event.reason} - {event.message}")
                        except Exception as e:
                            logger.info(f"[Test agent] DEBUG: Failed to get events for {pod_name}: {e}")

                        # Add debugging sleep for manual inspection
                        if "CI" in __import__("os").environ:
                            logger.info(f"[Test agent] DEBUG: SLEEPING 10 minutes for manual pod debugging - pod {pod_name} will remain available")
                            print(f"[Test agent] DEBUG: SLEEPING 10 minutes for manual pod debugging - pod {pod_name} will remain available")
                            print(f"[Test agent] DEBUG: Connect and run: kubectl logs {pod_name} -n {namespace}")
                            print(f"[Test agent] DEBUG: Connect and run: kubectl exec -it {pod_name} -n {namespace} -- sh")
                            __import__("time").sleep(600)  # 10 minute debugging window

                except Exception as e:
                    logger.info(f"[Test agent] DEBUG: Failed to check pods: {e}")
                    print(f"[Test agent] DEBUG: Failed to check pods: {e}")

            except Exception as debug_error:
                logger.info(f"[Test agent] DEBUG: Debug collection failed: {debug_error}")
                print(f"[Test agent] DEBUG: Debug collection failed: {debug_error}")

            raise Exception("Daemonset not ready - pods failing health checks. Check debug output above.")

        w = watch.Watch()
        for event in w.stream(
            func=self.list_namespaced_pod,
            namespace=namespace,
            label_selector="app=datadog",
            timeout_seconds=60,
        ):
            if "status" in event["object"] and event["object"]["status"]["phase"] == "Running":
                w.stop()
                logger.info("Datadog test agent started!")
                break

    @retry(delay=1, tries=5)
    def list_namespaced_pod(self, namespace, **kwargs):
        """Necessary to retry the list_namespaced_pod call in case of error (used by watch stream)"""
        return self.k8s_cluster_info.core_v1_api().list_namespaced_pod(namespace, **kwargs)

    def _wait_for_cluster_agent_ready(self, namespace, label_selector="app=datadog-cluster-agent"):
        cluster_agent_ready = False
        cluster_agent_status = None
        datadog_cluster_name = None

        for i in range(20):
            try:
                if datadog_cluster_name is None:
                    pods = self.k8s_cluster_info.core_v1_api().list_namespaced_pod(
                        namespace, label_selector=label_selector
                    )
                    datadog_cluster_name = pods.items[0].metadata.name if pods and len(pods.items) > 0 else None
                    logger.info(f"[status cluster agent] Cluster agent name: {datadog_cluster_name}")
                cluster_agent_status = (
                    self.k8s_cluster_info.core_v1_api().read_namespaced_pod_status(
                        name=datadog_cluster_name, namespace=namespace
                    )
                    if datadog_cluster_name
                    else None
                )
                if (
                    cluster_agent_status
                    and cluster_agent_status.status.phase == "Running"
                    and cluster_agent_status.status.container_statuses[0].ready == True
                ):
                    logger.info("[sattus cluster agent] Cluster agent datadog running!")
                    cluster_agent_ready = True
                    break
            except Exception as e:
                logger.info(f"Error waiting for cluster agent: {e}")
                datadog_cluster_name = None
            time.sleep(5)

        if not cluster_agent_ready:
            logger.error("Cluster agent not created. Last status: %s" % cluster_agent_status)
            if datadog_cluster_name:
                cluster_agent_logs = self.k8s_cluster_info.core_v1_api().read_namespaced_pod_log(
                    name=datadog_cluster_name, namespace=namespace
                )
                logger.error(f"Cluster agent logs: {cluster_agent_logs}")
            raise Exception("Cluster agent not created")
        # At this point the cluster_agent should be ready, we are going to wait a little bit more
        # to make sure the cluster_agent is ready (some times the cluster_agent is ready but the cluster agent is not ready yet)
        time.sleep(5)

    def export_debug_info(self, namespace):
        """Exports debug information for the test agent and the cluster_agent.
        We shouldn't raise any exception here, we just log the errors.
        """
        # Export all kind cluster logs
        try:
            if "kind" in self.k8s_cluster_info.context_name:
                execute_command(f"kind export logs {self.output_folder}/ --name {self.k8s_cluster_info.cluster_name}")
        except Exception as e:
            logger.error(f"Error exporting kind logs: {e}")

        # Get all pods
        ret = self.k8s_cluster_info.core_v1_api().list_namespaced_pod(namespace, watch=False)
        if ret is not None:
            for i in ret.items:
                k8s_logger(self.output_folder, "get.pods").info(
                    "%s\t%s\t%s" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name)
                )
                execute_command(
                    f"kubectl get event --field-selector involvedObject.name={i.metadata.name}",
                    logfile=f"{self.output_folder}/{i.metadata.name}_events.log",
                )

        # Get all deployments
        deployments = self.k8s_cluster_info.apps_api().list_deployment_for_all_namespaces()
        if deployments is not None:
            for deployment in deployments.items:
                k8s_logger(self.output_folder, "get.deployments").info(deployment)

        # Cluster logs, admission controller
        try:
            # Daemonset describe
            api_response = self.k8s_cluster_info.apps_api().read_namespaced_daemon_set(
                name="datadog", namespace=namespace
            )
            k8s_logger(self.output_folder, "daemon.set.describe").info(api_response)

            pods = self.k8s_cluster_info.core_v1_api().list_namespaced_pod(
                namespace, label_selector="app=datadog-cluster-agent"
            )
            assert len(pods.items) > 0, "No pods found for app datadog-cluster-agent"
            api_response = self.k8s_cluster_info.core_v1_api().read_namespaced_pod_log(
                name=pods.items[0].metadata.name, namespace=namespace
            )
            k8s_logger(self.output_folder, "datadog-cluster-agent").info(api_response)

            # Export: Telemetry datadog-cluster-agent
            execute_command(
                f"kubectl exec -it {pods.items[0].metadata.name} -- agent telemetry ",
                logfile=f"{self.output_folder}/{pods.items[0].metadata.name}_telemetry.log",
            )

            # Export: Status datadog-cluster-agent
            # Sometimes this command fails. Ignore this error
            execute_command(
                f"kubectl exec -it {pods.items[0].metadata.name} -- agent status || true ",
                logfile=f"{self.output_folder}/{pods.items[0].metadata.name}_status.log",
            )
        except Exception as e:
            logger.error(f"Error exporting datadog-cluster-agent logs: {e}")


def split_docker_image(image_reference):
    if ":" in image_reference:
        reference, tag = image_reference.rsplit(":", 1)
    else:
        reference, tag = image_reference, None
    return reference, tag


def add_cluster_agent_img_operator_yaml(image_tag, output_directory):
    operator_template = "utils/k8s_lib_injection/resources/operator/datadog-operator.yaml"
    # Read the input YAML file
    with open(operator_template) as file:
        yaml_data = yaml.safe_load(file)

    # Override the operator spec for cluster image
    yaml_data["spec"]["override"] = {}
    yaml_data["spec"]["override"]["clusterAgent"] = {}
    cluster_agent_image_spec = {"name": image_tag}
    if PrivateRegistryConfig.is_configured():
        cluster_agent_image_spec["pullSecrets"] = [{"name": "private-registry-secret"}]

    yaml_data["spec"]["override"]["clusterAgent"]["image"] = cluster_agent_image_spec
    # Construct the output file path (the folder should already exist)
    output_file = os.path.join(output_directory, Path(operator_template).name)

    # Write the modified YAML to the new file
    with open(output_file, "w") as file:
        yaml.dump(yaml_data, file, default_flow_style=False, encoding="utf-8")

    return output_file
