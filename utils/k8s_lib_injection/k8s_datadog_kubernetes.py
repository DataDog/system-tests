import time

from kubernetes import client, watch
from utils.tools import logger
from utils.k8s_lib_injection.k8s_command_utils import (
    helm_add_repo,
    helm_install_chart,
    execute_command,
)
from utils.k8s_lib_injection.k8s_logger import k8s_logger
from retry import retry


class K8sDatadog:
    def __init__(self, output_folder):
        self.output_folder = output_folder

    def configure(self, k8s_cluster_info, dd_cluster_feature={}, dd_cluster_uds=None, dd_cluster_version=None):
        self.k8s_cluster_info = k8s_cluster_info
        self.dd_cluster_feature = dd_cluster_feature
        self.dd_cluster_uds = dd_cluster_uds
        self.dd_cluster_version = dd_cluster_version
        logger.info(f"K8sDatadog configured with cluster: {self.k8s_cluster_info.cluster_name}")

    def deploy_test_agent(self, namespace="default"):
        """Installs the test agent pod."""

        logger.info(f"[Test agent] Deploying Datadog test agent on the cluster: {self.k8s_cluster_info.cluster_name}")
        # TODO RMM SET PORTS FROM CLUSTER INFO
        container = client.V1Container(
            name="trace-agent",
            image="ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:latest",
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
                initial_delay_seconds=1,
                period_seconds=2,
                timeout_seconds=10,
                success_threshold=1,
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

    def deploy_datadog_cluster_agent(self, namespace="default"):
        """Installs the Datadog Cluster Agent via helm for manual library injection testing.
        It returns when the Cluster Agent pod is ready.
        """

        logger.info("[Deploy datadog cluster] Deploying Datadog Cluster Agent with Admission Controler")
        operator_file = "utils/k8s_lib_injection/resources/operator/operator-helm-values.yaml"
        if self.dd_cluster_uds:
            logger.info("[Deploy datadog cluster] Using UDS")
            operator_file = "utils/k8s_lib_injection/resources/operator/operator-helm-values-uds.yaml"

        logger.info("[Deploy datadog cluster] Configuring helm repository")
        helm_add_repo("datadog", "https://helm.datadoghq.com", self.k8s_cluster_info, update=True)

        logger.info(f"[Deploy datadog cluster]helm install datadog with config file [{operator_file}]")

        # Add the cluster agent tag version
        self.dd_cluster_feature["clusterAgent.image.tag"] = self.dd_cluster_version
        helm_install_chart(
            self.k8s_cluster_info,
            "datadog",
            "datadog/datadog",
            value_file=operator_file,
            set_dict=self.dd_cluster_feature,
        )

        logger.info("[Deploy datadog cluster] Waiting for the cluster to be ready")
        self._wait_for_operator_ready(namespace)

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
            raise Exception("Daemonset not created")

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

    # TODO RMM rename this method
    @retry(delay=1, tries=5)
    def list_namespaced_pod(self, namespace, **kwargs):
        return self.k8s_cluster_info.core_v1_api().list_namespaced_pod(namespace, **kwargs)

    def _wait_for_operator_ready(self, namespace):
        operator_ready = False
        operator_status = None
        datadog_cluster_name = None

        for i in range(20):
            try:
                if datadog_cluster_name is None:
                    pods = self.k8s_cluster_info.core_v1_api().list_namespaced_pod(
                        namespace, label_selector="app=datadog-cluster-agent"
                    )
                    datadog_cluster_name = pods.items[0].metadata.name if pods and len(pods.items) > 0 else None
                operator_status = (
                    self.k8s_cluster_info.core_v1_api().read_namespaced_pod_status(
                        name=datadog_cluster_name, namespace=namespace
                    )
                    if datadog_cluster_name
                    else None
                )
                if (
                    operator_status
                    and operator_status.status.phase == "Running"
                    and operator_status.status.container_statuses[0].ready == True
                ):
                    logger.info("[Deploy operator] Operator datadog running!")
                    operator_ready = True
                    break
            except Exception as e:
                logger.info(f"Error waiting for operator: {e}")
            time.sleep(5)

        if not operator_ready:
            logger.error("Operator not created. Last status: %s" % operator_status)
            if datadog_cluster_name:
                operator_logs = self.k8s_cluster_info.core_v1_api().read_namespaced_pod_log(
                    name=datadog_cluster_name, namespace=namespace
                )
                logger.error(f"Operator logs: {operator_logs}")
            raise Exception("Operator not created")
        # At this point the operator should be ready, we are going to wait a little bit more
        # to make sure the operator is ready (some times the operator is ready but the cluster agent is not ready yet)
        time.sleep(5)

    def export_debug_info(self, namespace):
        """Exports debug information for the test agent and the operator.
        We shouldn't raise any exception here, we just log the errors.
        """

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

        # Daemonset describe
        api_response = self.k8s_cluster_info.apps_api().read_namespaced_daemon_set(name="datadog", namespace=namespace)
        k8s_logger(self.output_folder, "daemon.set.describe").info(api_response)

        # Cluster logs, admission controller
        try:
            pods = self.k8s_cluster_info.core_v1_api().list_namespaced_pod(
                namespace, label_selector="app=datadog-cluster-agent"
            )
            assert len(pods.items) > 0, "No pods found for app datadog-cluster-agent"
            api_response = self.core_v1_api().read_namespaced_pod_log(
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
