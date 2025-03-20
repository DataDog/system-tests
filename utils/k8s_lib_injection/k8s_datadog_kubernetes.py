import os
import time
import yaml
import re
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


class K8sDatadog:
    def __init__(self, library, library_init_image, injector_image, output_folder):
        self.library = library
        self.library_init_image = library_init_image
        self.injector_image = injector_image
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
        inject_by_annotations=True,
    ):
        self.k8s_cluster_info = k8s_cluster_info
        self.dd_cluster_feature = dd_cluster_feature
        self.dd_cluster_uds = dd_cluster_uds
        self.dd_cluster_version = dd_cluster_version
        self.dd_cluster_img = dd_cluster_img
        self.api_key = api_key
        self.app_key = app_key
        self.inject_by_annotations = inject_by_annotations
        if not self.inject_by_annotations:
            self.configure_inject_imgs_by_cluster_features()
        logger.info(f"K8sDatadog configured with cluster: {self.k8s_cluster_info.cluster_name}")

    def configure_inject_imgs_by_cluster_features(self):
        """We can set the injection images (lib-init and injector) as cluster configuration
        WARN: Currently in this mechanism we can not set the registry url, only the tag
        """
        library_lib = "js" if self.library == "nodejs" else self.library
        injection_images = {
            "datadog.apm.instrumentation.injector.imageTag": self._extract_tag(self.injector_image),
        }
        # If in the cluster_features configured by the scenario there are not entries
        # like "apm_config.instrumentation.targets" we can set the lib init. Both config are the same time are not compatible:
        # failed to register APM Instrumentation webhook: failed to create auto instrumentation config:
        #   apm_config.instrumentation.lib_versions and apm_config.instrumentation.targets are mutually exclusive and cannot be set together
        if self._has_apm_targets(self.dd_cluster_feature):
            # Workaround: to specify ie apm_config.instrumentation.targets[0].ddTraceVersions.python="latest" we are using a string to replace
            # by the current library and the tag of lib-init setted by the command line. ie:
            # "clusterAgent.datadog_cluster_yaml.apm_config.instrumentation.targets[0].ddTraceVersions.#k8s-library#": "#k8s-lib-init-img#"
            # Replace these wildcards for the current values
            self._replace_wildcards_apm_targets(self.dd_cluster_feature)
        else:
            injection_images.update(
                {f"datadog.apm.instrumentation.libVersions.{library_lib}": self._extract_tag(self.library_init_image)}
            )

        self.dd_cluster_feature.update(injection_images)

        logger.info("Injection images configured using datadog cluster agent")
        logger.debug(self.dd_cluster_feature)

    def _has_apm_targets(self, data):
        """Check if the dictionary contains any keys starting with the target key"""
        target_key = "clusterAgent.datadog_cluster_yaml.apm_config.instrumentation.targets"
        return any(key.startswith(target_key) for key in data.keys())  # noqa: SIM118

    def _replace_wildcards_apm_targets(self, data):
        """Recursively replace wildcards in dictionary keys and values in-place"""
        library_lib = "js" if self.library == "nodejs" else self.library
        keys_to_update = list(data.keys())  # Copy keys to avoid modifying while iterating

        for key in keys_to_update:
            value = data.pop(key)  # Remove old key
            # Replace wildcards in the key
            new_key = key.replace("#k8s-library#", library_lib).replace(
                "#k8s-lib-init-img#", self._extract_tag(self.library_init_image)
            )

            # Replace wildcards in the value
            if isinstance(value, str):
                new_value = value.replace("#k8s-library#", library_lib).replace(
                    "#k8s-lib-init-img#", self._extract_tag(self.library_init_image)
                )
            elif isinstance(value, dict):
                self.replace_wildcards(value)  # Recursive replacement for nested dictionaries
                new_value = value
            else:
                new_value = value  # Keep non-string values unchanged

            data[new_key] = new_value  # Assign back to the original dictionary

    def _extract_tag(self, image_url):
        """Extracts the tag from a container image URL."""
        match = re.search(r":([^:/]+)$", image_url)
        return match.group(1) if match else None

    def deploy_test_agent(self, namespace="default"):
        """Installs the test agent pod."""

        logger.info(f"[Test agent] Deploying Datadog test agent on the cluster: {self.k8s_cluster_info.cluster_name}")

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

        helm_install_chart(
            self.k8s_cluster_info,
            "datadog",
            "datadog/datadog",
            value_file=operator_file,
            set_dict=self.dd_cluster_feature,
        )

        logger.info("[Deploy datadog cluster] Waiting for the cluster to be ready")
        self._wait_for_cluster_agent_ready(namespace)

    def deploy_datadog_operator(self, namespace="default"):
        """Datadog Operator is a Kubernetes Operator that enables you to deploy and configure the Datadog Agent in a Kubernetes environment.
        By using the Datadog Operator, you can use a single Custom Resource Definition (CRD) to deploy the node-based Agent,
        the Datadog Cluster Agent, and Cluster check runners.
        """
        logger.info("[Deploy datadog operator] Configuring helm repository")
        helm_add_repo("datadog", "https://helm.datadoghq.com", self.k8s_cluster_info, update=True)
        helm_install_chart(
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
    yaml_data["spec"]["override"]["clusterAgent"]["image"] = {"name": image_tag}

    # Construct the output file path (the folder should already exist)
    output_file = os.path.join(output_directory, Path(operator_template).name)

    # Write the modified YAML to the new file
    with open(output_file, "w") as file:
        yaml.dump(yaml_data, file, default_flow_style=False, encoding="utf-8")

    return output_file
