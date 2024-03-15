import time
from kubernetes import client, config, watch
from kubernetes.utils import create_from_yaml
from utils.tools import logger
from utils.k8s_lib_injection.k8s_command_utils import (
    helm_add_repo,
    helm_install_chart,
    execute_command_sync,
    path_clusterrole,
)
from utils.k8s_lib_injection.k8s_logger import k8s_logger

import os
import json


class K8sDatadogClusterTestAgent:
    def __init__(self, prefix_library_init_image):
        self.k8s_kind_cluster = None
        self.prefix_library_init_image = prefix_library_init_image

    def configure(self, k8s_kind_cluster):
        self.k8s_kind_cluster = k8s_kind_cluster

    def desploy_test_agent(self):
        """ Installs the test agent pod."""

        logger.info(f"[Test agent] Deploying Datadog test agent on the cluster: {self.k8s_kind_cluster.cluster_name}")

        apps_api = client.AppsV1Api(
            api_client=config.new_client_from_config(context=self.k8s_kind_cluster.context_name)
        )
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

        apps_api.create_namespaced_daemon_set(namespace="default", body=daemonset)
        self.wait_for_test_agent()
        logger.info("[Test agent] Daemonset created")

    def deploy_operator_manual(self, use_uds=False):
        """ Installs the Datadog Cluster Agent via helm for manual library injection testing.
            It returns when the Cluster Agent pod is ready."""

        logger.info("[Deploy operator] Deploying Datadog Operator")

        operator_file = "utils/k8s_lib_injection/resources/operator/operator-helm-values.yaml"
        if use_uds:
            logger.info("[Deploy operator] Using UDS")
            operator_file = "utils/k8s_lib_injection/resources/operator/operator-helm-values-uds.yaml"

        logger.info("[Deploy operator] Configuring helm repository")
        helm_add_repo("datadog", "https://helm.datadoghq.com", self.k8s_kind_cluster, update=True)

        logger.info(f"[Deploy operator] helm install datadog with config file [{operator_file}]")

        helm_install_chart(
            self.k8s_kind_cluster,
            "datadog",
            "datadog/datadog",
            value_file=operator_file,
            set_dict={"datadog.apiKey": os.getenv("DD_API_KEY"), "datadog.appKey": os.getenv("DD_APP_KEY")},
        )

        logger.info("[Deploy operator] Waiting for the operator to be ready")
        self._wait_for_operator_ready()

    def deploy_operator_auto(self):
        """ Installs the Datadog Cluster Agent via helm for auto library injection testing.
            It returns when the Cluster Agent pod is ready."""

        logger.info("[Deploy operator] Using Patcher")
        operator_file = "utils/k8s_lib_injection/resources/operator/operator-helm-values-auto.yaml"

        self.create_configmap_auto_inject()
        logger.info("[Deploy operator] Configuring helm repository")
        helm_add_repo("datadog", "https://helm.datadoghq.com", self.k8s_kind_cluster, update=True)

        logger.info(f"[Deploy operator] helm install datadog with config file [{operator_file}]")

        helm_install_chart(
            self.k8s_kind_cluster,
            "datadog",
            "datadog/datadog",
            value_file=operator_file,
            set_dict={"datadog.apiKey": os.getenv("DD_API_KEY"), "datadog.appKey": os.getenv("DD_APP_KEY")},
            prefix_library_init_image=self.prefix_library_init_image,
        )
        self._wait_for_operator_ready()

        # TODO: This is a hack until the patching permission is added in the official helm chart.
        logger.info("[Deploy operator] adding patch permissions to the datadog-cluster-agent clusterrole")
        path_clusterrole(self.k8s_kind_cluster)

        self._wait_for_operator_ready()

    def apply_config_auto_inject(self, config_data):
        """ Applies an configuration change for auto injection.
            It returns when the targeted deployment finishes the rollout."""

        logger.info(f"[Auto Config] Applying config for auto-inject: {config_data}")
        v1 = client.CoreV1Api(api_client=config.new_client_from_config(context=self.k8s_kind_cluster.context_name))
        metadata = client.V1ObjectMeta(name="auto-instru", namespace="default",)
        configmap = client.V1ConfigMap(kind="ConfigMap", data={"auto-instru.json": config_data,}, metadata=metadata)
        r = v1.replace_namespaced_config_map(name="auto-instru", namespace="default", body=configmap)
        logger.info(f"[Auto Config] Configmap replaced!")
        time.sleep(90)

    def create_configmap_auto_inject(self):
        """ Minimal configuration needed when we install operator auto """
        logger.info("[Auto Config] Creating configmap for auto-inject")
        v1 = client.CoreV1Api(api_client=config.new_client_from_config(context=self.k8s_kind_cluster.context_name))
        metadata = client.V1ObjectMeta(name="auto-instru", namespace="default",)
        configmap = client.V1ConfigMap(
            kind="ConfigMap",
            data={
                "auto-instru.json": """| 
                []""",
            },
            metadata=metadata,
        )
        v1.create_namespaced_config_map(namespace="default", body=configmap)
        time.sleep(5)

    def wait_for_test_agent(self):
        v1 = client.CoreV1Api(api_client=config.new_client_from_config(context=self.k8s_kind_cluster.context_name))
        apps_api = client.AppsV1Api(
            api_client=config.new_client_from_config(context=self.k8s_kind_cluster.context_name)
        )
        daemonset_created = False
        daemonset_status = None
        # Wait for the daemonset to be created
        for i in range(10):
            try:
                daemonset_status = apps_api.read_namespaced_daemon_set_status(name="datadog", namespace="default")
                if daemonset_status.status.number_ready > 0:
                    logger.info(f"[Test agent] daemonset status datadog running!")
                    daemonset_created = True
                    break
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
                logger.info("Datadog test agent started!")
                break

    def _wait_for_operator_ready(self):
        v1 = client.CoreV1Api(api_client=config.new_client_from_config(context=self.k8s_kind_cluster.context_name))
        pods = v1.list_namespaced_pod(namespace="default", label_selector="app=datadog-cluster-agent")
        datadog_cluster_name = pods.items[0].metadata.name

        operator_ready = False
        for i in range(15):
            try:
                operator_status = v1.read_namespaced_pod_status(name=datadog_cluster_name, namespace="default")
                if (
                    operator_status.status.phase == "Running"
                    and operator_status.status.container_statuses[0].ready == True
                ):
                    logger.info(f"[Deploy operator] Operator datadog running!")
                    operator_ready = True
                    break
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

    def export_debug_info(self, output_folder, test_name):
        """ Exports debug information for the test agent and the operator."""
        v1 = client.CoreV1Api(api_client=config.new_client_from_config(context=self.k8s_kind_cluster.context_name))
        api = client.AppsV1Api(api_client=config.new_client_from_config(context=self.k8s_kind_cluster.context_name))
        event_api = client.EventsV1Api(
            api_client=config.new_client_from_config(context=self.k8s_kind_cluster.context_name)
        )

        # Get all pods
        ret = v1.list_pod_for_all_namespaces(watch=False)
        for i in ret.items:
            k8s_logger(output_folder, test_name, "get.pods").info(
                "%s\t%s\t%s" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name)
            )

        # Get all deployments
        deployments = api.list_deployment_for_all_namespaces()
        for deployment in deployments.items:
            k8s_logger(output_folder, test_name, "get.deployments").info(deployment)

        # Daemonset describe
        try:
            api_response = api.read_namespaced_daemon_set(name="datadog", namespace="default")
            k8s_logger(output_folder, test_name, "daemon.set.describe").info(api_response)
        except Exception as e:
            k8s_logger(output_folder, test_name, "daemon.set.describe").info(
                "Exception when calling CoreV1Api->read_namespaced_daemon_set: %s\n" % e
            )

        # Cluster logs, admission controller
        try:
            pods = v1.list_namespaced_pod(namespace="default", label_selector="app=datadog-cluster-agent")
            if len(pods.items) > 0:
                api_response = v1.read_namespaced_pod_log(name=pods.items[0].metadata.name, namespace="default")
                k8s_logger(output_folder, test_name, "datadog-cluster-agent").info(api_response)

                # Export: Telemetry datadog-cluster-agent
                execute_command_sync(
                    f"kubectl exec -it {pods.items[0].metadata.name} -- agent telemetry > '{output_folder}/{pods.items[0].metadata.name}_telemetry.log'",
                    self.k8s_kind_cluster,
                )

                # Export: Status datadog-cluster-agent
                # Sometimes this command fails. Ignore this error
                execute_command_sync(
                    f"kubectl exec -it {pods.items[0].metadata.name} -- agent status > '{output_folder}/{pods.items[0].metadata.name}_status.log' || true ",
                    self.k8s_kind_cluster,
                )
        except Exception as e:
            k8s_logger(output_folder, test_name, "daemon.set.describe").info(
                "Exception when calling CoreV1Api->datadog-cluster-agent logs: %s\n" % e
            )

        events = event_api.list_event_for_all_namespaces(pretty="pretty_example")
        k8s_logger(output_folder, test_name, "pod.events").info(events)
