import time
from kubernetes import client, config, watch
from kubernetes.utils import create_from_yaml
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
    def __init__(self, prefix_library_init_image, output_folder, test_name):
        self.k8s_kind_cluster = None
        self.prefix_library_init_image = prefix_library_init_image
        self.output_folder = output_folder
        self.test_name = test_name
        self.logger = None

    def configure(self, k8s_kind_cluster):
        self.k8s_kind_cluster = k8s_kind_cluster
        self.logger = k8s_logger(self.output_folder, self.test_name, "k8s_logger")
        self.logger.info(f"K8sDatadogClusterTestAgent configured with cluster: {self.k8s_kind_cluster.cluster_name}")

    def get_k8s_api(self):
        """ Get the k8s api. It retries 5 times if it fails. Sometimes there are 
        collisions when we execute a lot of tests in parallel."""
        for i in range(5):
            try:
                return self._k8s_api()
            except Exception as e:
                self.logger.info(f"Error getting k8s api: {e}")
                time.sleep(2)
        raise Exception("Error getting k8s api")

    def _k8s_api(self):
        v1 = client.CoreV1Api(api_client=config.new_client_from_config(context=self.k8s_kind_cluster.context_name))
        apps_api = client.AppsV1Api(
            api_client=config.new_client_from_config(context=self.k8s_kind_cluster.context_name)
        )
        return v1, apps_api

    def desploy_test_agent(self):
        """ Installs the test agent pod."""

        self.logger.info(
            f"[Test agent] Deploying Datadog test agent on the cluster: {self.k8s_kind_cluster.cluster_name}"
        )

        _, apps_api = self.get_k8s_api()
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
        try:
            apps_api.create_namespaced_daemon_set(namespace="default", body=daemonset)
        except client.exceptions.ApiException as e:
            # Ok, let's try again
            time.sleep(5)
            _, apps_api = self.get_k8s_api()
            apps_api.create_namespaced_daemon_set(namespace="default", body=daemonset)

        self.wait_for_test_agent()
        self.logger.info("[Test agent] Daemonset created")

    def deploy_operator_manual(self, use_uds=False):
        """ Installs the Datadog Cluster Agent via helm for manual library injection testing.
            It returns when the Cluster Agent pod is ready."""

        self.logger.info("[Deploy operator] Deploying Datadog Operator")

        operator_file = "utils/k8s_lib_injection/resources/operator/operator-helm-values.yaml"
        if use_uds:
            self.logger.info("[Deploy operator] Using UDS")
            operator_file = "utils/k8s_lib_injection/resources/operator/operator-helm-values-uds.yaml"

        self.logger.info("[Deploy operator] Configuring helm repository")
        helm_add_repo("datadog", "https://helm.datadoghq.com", self.k8s_kind_cluster, update=True)

        self.logger.info(f"[Deploy operator] helm install datadog with config file [{operator_file}]")

        helm_install_chart(
            self.k8s_kind_cluster,
            "datadog",
            "datadog/datadog",
            value_file=operator_file,
            set_dict={"datadog.apiKey": os.getenv("DD_API_KEY"), "datadog.appKey": os.getenv("DD_APP_KEY")},
        )

        self.logger.info("[Deploy operator] Waiting for the operator to be ready")
        self._wait_for_operator_ready()

    def deploy_operator_auto(self):
        """ Installs the Datadog Cluster Agent via helm for auto library injection testing.
            It returns when the Cluster Agent pod is ready."""

        self.logger.info("[Deploy operator] Using Patcher")
        operator_file = "utils/k8s_lib_injection/resources/operator/operator-helm-values-auto.yaml"

        self.create_configmap_auto_inject()
        self.logger.info("[Deploy operator] Configuring helm repository")
        helm_add_repo("datadog", "https://helm.datadoghq.com", self.k8s_kind_cluster, update=True)

        self.logger.info(f"[Deploy operator] helm install datadog with config file [{operator_file}]")

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
        self.logger.info("[Deploy operator] adding patch permissions to the datadog-cluster-agent clusterrole")
        path_clusterrole(self.k8s_kind_cluster)

        self._wait_for_operator_ready()

    def apply_config_auto_inject(self, config_data, rev=0):
        """ Applies an configuration change for auto injection.
            It returns when the targeted deployment finishes the rollout."""

        self.logger.info(f"[Auto Config] Applying config for auto-inject: {config_data}")
        v1, _ = self.get_k8s_api()
        metadata = client.V1ObjectMeta(name="auto-instru", namespace="default",)
        configmap = client.V1ConfigMap(kind="ConfigMap", data={"auto-instru.json": config_data,}, metadata=metadata)
        r = v1.replace_namespaced_config_map(name="auto-instru", namespace="default", body=configmap)
        self.logger.info(f"[Auto Config] Configmap replaced!")
        k8s_logger(self.output_folder, self.test_name, "applied_configmaps").info(r)
        self.wait_configmap_auto_inject(timeout=100, rev=rev)

    def create_configmap_auto_inject(self):
        """ Minimal configuration needed when we install operator auto """
        self.logger.info("[Auto Config] Creating configmap for auto-inject")
        v1, _ = self.get_k8s_api()
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

    def wait_configmap_auto_inject(self, timeout=90, rev=0):
        """ wait for the configmap to be read by the datadog-cluster-agent."""
        patch_id = "11777398274940883092"
        self.logger.info("[Auto Config] Waiting for the configmap to be read by the datadog-cluster-agent.")
        # First we need to wait for the configmap to be created
        v1, _ = self.get_k8s_api()
        try:
            w = watch.Watch()
            for event in w.stream(func=v1.list_namespaced_config_map, namespace="default", timeout_seconds=timeout):
                k8s_logger(self.output_folder, self.test_name, "events_configmaps").info(event)
                if event["type"] == "ADDED" and event["object"].metadata.name == "auto-instru":
                    self.logger.info("[Auto Config] Configmap applied!")
                    w.stop()
                    break
        except Exception as e:
            self.logger.error(f"[Auto Config] Error waiting for the configmap: {e}")

        # Second wait for datadog-cluster-agent read the configmap
        expected_log = f'Applying Remote Config ID "{patch_id}" with revision "{rev}" and action'
        pod_cluster_agent_name = None
        timeout = time.time() + timeout
        while True:
            try:
                if pod_cluster_agent_name is None:
                    pods = v1.list_namespaced_pod(namespace="default", label_selector="app=datadog-cluster-agent")
                    assert len(pods.items) > 0, "No pods found for app datadog-cluster-agent"
                    pod_cluster_agent_name = pods.items[0].metadata.name
                api_response = v1.read_namespaced_pod_log(name=pod_cluster_agent_name, namespace="default")
                for log_line in api_response.splitlines():
                    if log_line.find(expected_log) != -1:
                        self.logger.info(f"Configmap read by datadog-cluster-agent: {log_line}")
                        return
            except Exception as e:
                self.logger.error(
                    f"[Auto Config] Error waiting for the datadog-cluster-agent to read the configmap: {e}"
                )
            if time.time() > timeout:
                self.logger.error(f"Timeout waiting for the datadog-cluster-agent to read the configmap")
                raise TimeoutError("Timeout waiting for the datadog-cluster-agent to read the configmap")
            time.sleep(5)

    def wait_for_test_agent(self):
        v1, apps_api = self.get_k8s_api()
        daemonset_created = False
        daemonset_status = None
        # Wait for the daemonset to be created
        for i in range(20):
            try:
                daemonset_status = apps_api.read_namespaced_daemon_set_status(name="datadog", namespace="default")
                if daemonset_status.status.number_ready > 0:
                    self.logger.info(f"[Test agent] daemonset status datadog running!")
                    daemonset_created = True
                    break
                time.sleep(5)
            except client.exceptions.ApiException as e:
                self.logger.info(f"[Test agent] daemonset status error: {e}")
                time.sleep(5)

        if not daemonset_created:
            self.logger.info("[Test agent] Daemonset not created. Last status: %s" % daemonset_status)
            raise Exception("Daemonset not created")
        try:
            w = watch.Watch()
            for event in w.stream(
                func=v1.list_namespaced_pod, namespace="default", label_selector="app=datadog", timeout_seconds=60
            ):
                if event["object"].status.phase == "Running":
                    w.stop()
                    self.logger.info("Datadog test agent started!")
                    break
        except Exception as e:
            self.logger.error(f"Error waiting for the test agent: {e}")
            # Wait 10 second and continue. Sometimes we have conflict when we run a lot of tests in parallel
            time.sleep(10)

    def _wait_for_operator_ready(self):
        datadog_cluster_name = None
        v1, _ = self.get_k8s_api()
        operator_ready = False
        operator_status = None

        for i in range(20):
            try:
                if datadog_cluster_name is None:
                    pods = v1.list_namespaced_pod(namespace="default", label_selector="app=datadog-cluster-agent")
                    datadog_cluster_name = pods.items[0].metadata.name
                operator_status = v1.read_namespaced_pod_status(name=datadog_cluster_name, namespace="default")
                if (
                    operator_status.status.phase == "Running"
                    and operator_status.status.container_statuses[0].ready == True
                ):
                    self.logger.info(f"[Deploy operator] Operator datadog running!")
                    operator_ready = True
                    break
                time.sleep(5)
            except Exception as e:
                self.logger.info(f"Pod status error: {e}")
                time.sleep(5)

        if not operator_ready:
            self.logger.error("Operator not created. Last status: %s" % operator_status)
            operator_logs = v1.read_namespaced_pod_log(name=datadog_cluster_name, namespace="default")
            self.logger.error(f"Operator logs: {operator_logs}")
            raise Exception("Operator not created")
        # At this point the operator should be ready, we are going to wait a little bit more
        # to make sure the operator is ready (some times the operator is ready but the cluster agent is not ready yet)
        time.sleep(5)

    def export_debug_info(self):
        """ Exports debug information for the test agent and the operator."""
        v1, api = self.get_k8s_api()
        # Get all pods
        ret = v1.list_namespaced_pod(namespace="default", watch=False)
        for i in ret.items:
            k8s_logger(self.output_folder, self.test_name, "get.pods").info(
                "%s\t%s\t%s" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name)
            )
            execute_command_sync(
                f"kubectl get event --field-selector involvedObject.name={i.metadata.name}",
                self.k8s_kind_cluster,
                logfile=f"{self.output_folder}/{i.metadata.name}_events.log",
            )

        # Get all deployments
        deployments = api.list_deployment_for_all_namespaces()
        for deployment in deployments.items:
            k8s_logger(self.output_folder, self.test_name, "get.deployments").info(deployment)

        # Daemonset describe
        try:
            api_response = api.read_namespaced_daemon_set(name="datadog", namespace="default")
            k8s_logger(self.output_folder, self.test_name, "daemon.set.describe").info(api_response)
        except Exception as e:
            k8s_logger(self.output_folder, self.test_name, "daemon.set.describe").info(
                "Exception when calling CoreV1Api->read_namespaced_daemon_set: %s\n" % e
            )

        # Cluster logs, admission controller
        try:
            pods = v1.list_namespaced_pod(namespace="default", label_selector="app=datadog-cluster-agent")
            assert len(pods.items) > 0, "No pods found for app datadog-cluster-agent"
            api_response = v1.read_namespaced_pod_log(name=pods.items[0].metadata.name, namespace="default")
            k8s_logger(self.output_folder, self.test_name, "datadog-cluster-agent").info(api_response)

            # Export: Telemetry datadog-cluster-agent
            execute_command_sync(
                f"kubectl exec -it {pods.items[0].metadata.name} -- agent telemetry ",
                self.k8s_kind_cluster,
                logfile=f"{self.output_folder}/{pods.items[0].metadata.name}_telemetry.log",
            )

            # Export: Status datadog-cluster-agent
            # Sometimes this command fails. Ignore this error
            execute_command_sync(
                f"kubectl exec -it {pods.items[0].metadata.name} -- agent status || true ",
                self.k8s_kind_cluster,
                logfile=f"{self.output_folder}/{pods.items[0].metadata.name}_status.log",
            )
        except Exception as e:
            k8s_logger(self.output_folder, self.test_name, "daemon.set.describe").info(
                "Exception when calling CoreV1Api->datadog-cluster-agent logs: %s\n" % e
            )
