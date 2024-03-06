import time
from kubernetes import client, watch
from kubernetes.utils import create_from_yaml
from utils.tools import logger
from utils.k8s_lib_injection.k8s_command_utils import helm_add_repo, helm_install_chart, execute_command
import os
import json


class K8sDatadogClusterTestAgent:
    def desploy_test_agent(self):
        """ Installs the test agent pod."""

        logger.info("[Test agent] Deploying Datadog test agent")
        apps_api = client.AppsV1Api()
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

        result = apps_api.create_namespaced_daemon_set(namespace="default", body=daemonset)
        self.wait_for_test_agent()
        logger.info("[Test agent] Daemonset created")

    def deploy_operator_manual(self, use_uds=False):
        """ Installs the Datadog Cluster Agent via helm for manual library injection testing.
            It returns when the Cluster Agent pod is ready."""

        v1 = client.CoreV1Api()

        logger.info("[Deploy operator] Deploying Datadog Operator")

        operator_file = "utils/k8s_lib_injection/resources/operator/operator-helm-values.yaml"
        if use_uds:
            logger.info("[Deploy operator] Using UDS")
            operator_file = "utils/k8s_lib_injection/resources/operator/operator-helm-values-uds.yaml"

        logger.info("[Deploy operator] Configuring helm repository")
        helm_add_repo("datadog", "https://helm.datadoghq.com", update=True)

        logger.info(f"[Deploy operator] helm install datadog with config file [{operator_file}]")

        helm_install_chart(
            "datadog",
            "datadog/datadog",
            value_file=operator_file,
            set_dict={"datadog.apiKey": os.getenv("DD_API_KEY"), "datadog.appKey": os.getenv("DD_APP_KEY")},
        )

        logger.info("[Deploy operator] Waiting for the operator to be ready")
        pods = v1.list_namespaced_pod(namespace="default", label_selector="app=datadog-cluster-agent")

        datadog_cluster_name = pods.items[0].metadata.name
        logger.info(f"[Deploy operator] Waiting for the operator ready on cluster name: {datadog_cluster_name}")

        self._wait_for_operator_ready()

    def deploy_operator_auto(self, use_uds=False):
        """ Installs the Datadog Cluster Agent via helm for auto library injection testing.
            It returns when the Cluster Agent pod is ready."""

        logger.info("[Deploy operator] Using Patcher")
        operator_file = "utils/k8s_lib_injection/resources/operator/operator-helm-values-auto.yaml"

        self.create_configmap_auto_inject()
        logger.info("[Deploy operator] Configuring helm repository")
        helm_add_repo("datadog", "https://helm.datadoghq.com", update=True)

        logger.info(f"[Deploy operator] helm install datadog with config file [{operator_file}]")

        helm_install_chart(
            "datadog",
            "datadog/datadog",
            value_file=operator_file,
            set_dict={"datadog.apiKey": os.getenv("DD_API_KEY"), "datadog.appKey": os.getenv("DD_APP_KEY")},
        )
        self._wait_for_operator_ready()

        # TODO: This is a hack until the patching permission is added in the official helm chart.
        logger.info("[Deploy operator] adding patch permissions to the datadog-cluster-agent clusterrole")
        execute_command("sh utils/k8s_lib_injection/resources/operator/scripts/path_clusterrole.sh")

        v1 = client.CoreV1Api()

        self._wait_for_operator_ready()

    def apply_config_auto_inject(self, library, config_data):
        """ Applies an configuration change for auto injection.
            It returns when the targeted deployment finishes the rollout."""

        logger.info(f"[Auto Config] Applying config for auto-inject: {config_data}")
        v1 = client.CoreV1Api()
        metadata = client.V1ObjectMeta(name="auto-instru", namespace="default",)
        configmap = client.V1ConfigMap(kind="ConfigMap", data={"auto-instru.json": config_data,}, metadata=metadata)
        r = v1.replace_namespaced_config_map(name="auto-instru", namespace="default", body=configmap)
        logger.info(f"[Auto Config] Configmap replaced!")
        time.sleep(90)

    def create_configmap_auto_inject(self):
        """ Minimal configuration needed when we install operator auto """
        logger.info("[Auto Config] Creating configmap for auto-inject")
        v1 = client.CoreV1Api()
        metadata = client.V1ObjectMeta(name="auto-instru", namespace="default",)
        configmap = client.V1ConfigMap(
            kind="ConfigMap",
            data={
                "auto-instru.json": """| 
                []""",
            },
            metadata=metadata,
        )
        try:
            v1.create_namespaced_config_map(namespace="default", body=configmap)
        except Exception as e:
            logger.error("Exception when calling CoreV1Api->create_namespaced_config_map: %s\n" % e)
            raise e
        time.sleep(5)

    def wait_for_test_agent(self):
        v1 = client.CoreV1Api()
        apps_api = client.AppsV1Api()
        daemonset_created = False
        daemonset_status = None
        # Wait for the daemonset to be created
        for i in range(0, 10):
            try:
                daemonset_status = apps_api.read_namespaced_daemon_set_status(name="datadog", namespace="default")
                if daemonset_status.status.number_ready > 0:
                    logger.info(f"[Test agent] daemonset status datadog running!")
                    daemonset_created = True
                    break
                else:
                    time.sleep(5)
            except client.exceptions.ApiException as e:
                logger.info(f"[Test agent] daemonset status error: {e}")
                time.sleep(5)

        if not daemonset_created:
            logger.info("[Test agent] Daemonset not created. Last status: %s" % daemonset_status)
            raise Exception("Daemonset not created")

        w = watch.Watch()
        for event in w.stream(
            func=v1.list_namespaced_pod, namespace="default", label_selector="app=datadog", timeout_seconds=60
        ):
            if event["object"].status.phase == "Running":
                w.stop()
                end_time = time.time()
                logger.info("Datadog test agent started!")
                break

    def _wait_for_operator_ready(self):
        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace="default", label_selector="app=datadog-cluster-agent")
        datadog_cluster_name = pods.items[0].metadata.name

        operator_ready = False
        for i in range(0, 15):
            try:
                operator_status = v1.read_namespaced_pod_status(name=datadog_cluster_name, namespace="default")
                if (
                    operator_status.status.phase == "Running"
                    and operator_status.status.container_statuses[0].ready == True
                ):
                    logger.info(f"[Deploy operator] Operator datadog running!")
                    operator_ready = True
                    break
                else:
                    time.sleep(5)
            except client.exceptions.ApiException as e:
                logger.info(f"Pod status error: {e}")
                time.sleep(5)

        if not operator_ready:
            logger.error("Operator not created. Last status: %s" % operator_status)
            operator_logs = v1.read_namespaced_pod_log(name=datadog_cluster_name, namespace="default")
            logger.error(f"Operator logs: {operator_logs}")
            raise Exception("Operator not created")
        # At this point the operator should be ready, we are going to wait a little bit more to make sure the operator is ready (some times the operator is ready but the cluster agent is not ready yet)
        time.sleep(5)
