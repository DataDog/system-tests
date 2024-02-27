import time
from kubernetes import client, watch
from utils.tools import logger
from utils.k8s_lib_injection.k8s_command_utils import helm_add_repo, helm_install_chart
import os


class K8sDatadogClusterTestAgent:
    def desploy_test_agent(self):
        logger.info("Deploying Datadog test agent")
        v1 = client.CoreV1Api()
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

        daemonset_created = False
        daemonset_status = None
        # Wait for the daemonset to be created
        for i in range(0, 10):
            try:
                daemonset_status = apps_api.read_namespaced_daemon_set_status(name="datadog", namespace="default")
                if daemonset_status.status.number_ready > 0:
                    logger.info(f"daemonset status datadog running!")
                    daemonset_created = True
                    break
                else:
                    time.sleep(5)
            except client.exceptions.ApiException as e:
                logger.info(f"daemonset status error: {e}")
                time.sleep(5)

        if not daemonset_created:
            logger.info("Daemonset not created. Last status: %s" % daemonset_status)
            raise Exception("Daemonset not created")

        logger.info("Daemonset created")

        w = watch.Watch()
        for event in w.stream(
            func=v1.list_namespaced_pod, namespace="default", label_selector="app=datadog", timeout_seconds=60
        ):
            if event["object"].status.phase == "Running":
                w.stop()
                end_time = time.time()
                logger.info("Datadog test agent started!")
                break

    def deploy_operator_manual(self, use_uds=False):

        v1 = client.CoreV1Api()
        apps_api = client.AppsV1Api()
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
        logger.info(f"waiting for the operator ready on cluster name: {datadog_cluster_name}")

        pod_ready = False
        for i in range(0, 10):
            try:

                pod_status = v1.read_namespaced_pod_status(name=datadog_cluster_name, namespace="default")

                if pod_status.status.phase == "Running":
                    logger.info(f"Pod status datadog running!")
                    pod_ready = True
                    break
                else:
                    time.sleep(5)
            except client.exceptions.ApiException as e:
                logger.info(f"Pod status error: {e}")
                time.sleep(5)

        if not pod_ready:
            logger.error("Operator not created. Last status: %s" % pod_status)
            pod_logs = v1.read_namespaced_pod_log(name=datadog_cluster_name, namespace="default")
            logger.error(f"Operator logs: {pod_logs}")
            raise Exception("Operator not created")
