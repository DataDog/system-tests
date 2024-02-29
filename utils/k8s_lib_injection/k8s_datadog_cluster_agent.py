import time
from kubernetes import client, watch
from utils.tools import logger
from utils.k8s_lib_injection.k8s_command_utils import helm_add_repo, helm_install_chart, execute_command
import os
import json


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

        # operator_ready = False
        # w = watch.Watch()
        # for event in w.stream(
        #     func=v1.list_namespaced_pod, namespace="default", field_selector=f'metadata.name={datadog_cluster_name}', timeout_seconds=60
        # ):
        #     if event["object"].status.phase == "Running" and event["object"].status.container_statuses[0].ready:
        #         w.stop()
        #         logger.info("[Deploy operator] Operator started!")
        #         operator_ready = True
        #         break

        # if not operator_ready:
        #    pod_status = v1.read_namespaced_pod_status(name=datadog_cluster_name, namespace="default")
        #    logger.error("[Deploy operator] Operator not created. Last status: %s" % pod_status)
        #    pod_logs = v1.read_namespaced_pod_log(name=datadog_cluster_name, namespace="default")
        #    logger.error(f"[Deploy operator] Operator logs: {pod_logs}")
        #    raise Exception("[Deploy operator] Operator not created")

        self._wait_for_operator_ready()

    def _wait_for_operator_ready(self):
        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace="default", label_selector="app=datadog-cluster-agent")
        datadog_cluster_name = pods.items[0].metadata.name

        operator_ready = False
        for i in range(0, 10):
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

    def deploy_operator_auto(self, use_uds=False):
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

        # body_patch='[{"op": "add", "path": "/rules/0", "value":{ "apiGroups": ["apps"], "resources": ["deployments"], "verbs": ["patch"]}}]'
        # execute_command( f"kubectl patch clusterrole datadog-cluster-agent --type=json -p {body_patch} ")
        execute_command("sh utils/k8s_lib_injection/resources/operator/scripts/path_clusterrole.sh")
        # TODO: This is a hack until the patching permission is added in the official helm chart.
        # logger.info("[Deploy operator] adding patch permissions to the datadog-cluster-agent clusterrole")
        v1 = client.CoreV1Api()
        # apps_api = client.AppsV1Api()
        # logger.info("[Deploy operator] ---------------------------------- 1")
        # body_patch='[{"op": "add", "path": "/rules/0", "value":{ "apiGroups": ["apps"], "resources": ["deployments"], "verbs": ["patch"]}}]'
        # api_instance = client.RbacAuthorizationV1Api(v1)
        # logger.info("[Deploy operator] ---------------------------------- 2")
        # ret = api_instance.patch_cluster_role(name="datadog-cluster-agent", body=json.loads(body_patch))
        # logger.info("[Deploy operator] ---------------------------------- 3")
        # logger.info("[Deploy operator] Waiting for the operator to be ready")

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

    def create_configmap_auto_inject(self):
        exec_command = "kubectl create -f utils/k8s_lib_injection/resources/operator/templates/configmap.yaml"
        execute_command(exec_command)
        # Simple sleep. TODO: Add a better way to wait for the configmap to be created
        time.sleep(5)

    def apply_config_auto_inject(self):
        execute_command("kubectl apply -f lib-injection/build/docker/java/config.yaml")
        logger.info("[Auto Config] Waiting on the cluster agent to pick up the changes")
        time.sleep(120)
        logger.info("[Auto Config] apply-config-auto: waiting for deployments/test-java-deployment available")
        execute_command("kubectl rollout status deployments/test-java-deployment --timeout=5m")

    # TODO create configmap for auto-inject programatically
    def _create_configmap_auto_inject(self):
        v1 = client.CoreV1Api()
        # Configureate ConfigMap metadata
        metadata = client.V1ObjectMeta(name="auto-instru", namespace="default",)
        # Get File Content
        with open("utils/k8s_lib_injection/resources/operator/templates/configmap.yaml", "r") as f:
            file_content = f.read()
        # Instantiate the configmap object
        configmap = client.V1ConfigMap(
            api_version="v1", kind="ConfigMap", data=dict(test=file_content), metadata=metadata
        )

        try:
            api_response = v1.create_namespaced_config_map(namespace="default", body=configmap)
        except Exception as e:
            logger.error("Exception when calling CoreV1Api->create_namespaced_config_map: %s\n" % e)
            raise e
        # Simple sleep. TODO: Add a better way to wait for the configmap to be created
        time.sleep(5)
