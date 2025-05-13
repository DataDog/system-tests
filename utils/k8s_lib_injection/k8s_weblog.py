from kubernetes import client, watch
from utils._logger import logger
from utils.k8s_lib_injection.k8s_logger import k8s_logger
from retry import retry


class K8sWeblog:
    manual_injection_props = {
        "python": [
            {"name": "PYTHONPATH", "value": "/datadog-lib/"},
            {"name": "DD_INSTALL_DDTRACE_PYTHON", "value": "1"},
        ],
        "dotnet": [
            {"name": "CORECLR_ENABLE_PROFILING", "value": "1"},
            {"name": "CORECLR_PROFILER", "value": "{846F5F1C-F9AE-4B07-969E-05C26BC060D8}"},
            {"name": "CORECLR_PROFILER_PATH", "value": "/datadog-lib/Datadog.Trace.ClrProfiler.Native.so"},
            {"name": "DD_DOTNET_TRACER_HOME", "value": "/datadog-lib"},
            {"name": "LD_PRELOAD", "value": "/datadog-lib/continuousprofiler/Datadog.Linux.ApiWrapper.x64.so"},
        ],
        "java": [{"name": "JAVA_TOOL_OPTIONS", "value": "-javaagent:/datadog-lib/dd-java-agent.jar"}],
        "js": [{"name": "NODE_OPTIONS", "value": "--require=/datadog-lib/node_modules/dd-trace/init"}],
        "ruby": [{"name": "RUBYOPT", "value": " -r/datadog-lib/auto_inject"}],
        "php": [
            {"name": "PHP_INI_SCAN_DIR", "value": ":/datadog-lib/linux-gnu/loader"},
            {"name": "DD_LOADER_PACKAGE_PATH", "value": "/datadog-lib"},
        ],
    }

    def __init__(self, app_image, library, library_init_image, injector_image, output_folder):
        self.app_image = app_image
        self.library = library
        self.library_init_image = library_init_image
        self.injector_image = injector_image
        self.output_folder = output_folder

    def configure(self, k8s_cluster_info, weblog_env=None, dd_cluster_uds=None, service_account=None):
        self.weblog_env = weblog_env
        self.dd_cluster_uds = dd_cluster_uds
        self.dd_service_account = service_account
        self.k8s_cluster_info = k8s_cluster_info

    def _get_base_weblog_pod(self):
        """Installs a target app for manual library injection testing.
        It returns when the app pod is ready.
        """

        logger.info(
            "[Deploy weblog] Creating weblog pod configuration. weblog_variant_image: [%s], library: [%s], library_init_image: [%s]"
            % (self.app_image, self.library, self.library_init_image)
        )
        library_lib = "js" if self.library == "nodejs" else self.library
        pod_metadata = client.V1ObjectMeta(
            name="my-app",
            namespace="default",
            labels={
                "admission.datadoghq.com/enabled": "true",
                "app": "my-app",
                "tags.datadoghq.com/env": "local",
                "tags.datadoghq.com/service": "my-app",
                "tags.datadoghq.com/version": "local",
            },
            annotations={
                f"admission.datadoghq.com/{library_lib}-lib.custom-image": f"{self.library_init_image}",
                "admission.datadoghq.com/apm-inject.custom-image": f"{self.injector_image}",
            },
        )

        containers = []
        # Set the default environment variables for all pods
        default_pod_env = [
            client.V1EnvVar(name="SERVER_PORT", value="18080"),
            client.V1EnvVar(
                name="DD_ENV",
                value_from=client.V1EnvVarSource(
                    field_ref=client.V1ObjectFieldSelector(field_path="metadata.labels['tags.datadoghq.com/env']")
                ),
            ),
            client.V1EnvVar(
                name="DD_SERVICE",
                value_from=client.V1EnvVarSource(
                    field_ref=client.V1ObjectFieldSelector(field_path="metadata.labels['tags.datadoghq.com/service']")
                ),
            ),
            client.V1EnvVar(
                name="DD_VERSION",
                value_from=client.V1EnvVarSource(
                    field_ref=client.V1ObjectFieldSelector(field_path="metadata.labels['tags.datadoghq.com/version']")
                ),
            ),
            client.V1EnvVar(name="DD_TRACE_DEBUG", value="1"),
            client.V1EnvVar(name="DD_APM_INSTRUMENTATION_DEBUG", value="true"),
        ]
        # Add custom env vars if provided
        if self.weblog_env:
            for k, v in self.weblog_env.items():
                default_pod_env.append(client.V1EnvVar(name=k, value=v))

        logger.info(f"Weblog pod env: {default_pod_env}")
        container1 = client.V1Container(
            name="my-app",
            image=self.app_image,
            env=default_pod_env,
            readiness_probe=client.V1Probe(
                timeout_seconds=5,
                success_threshold=3,
                failure_threshold=10,
                http_get=client.V1HTTPGetAction(path="/", port=18080),
                initial_delay_seconds=15,
                period_seconds=10,
            ),
            ports=[client.V1ContainerPort(container_port=18080, host_port=18080, name="http", protocol="TCP")],
        )

        containers.append(container1)

        pod_spec = client.V1PodSpec(containers=containers, service_account=self.dd_service_account)

        pod_body = client.V1Pod(api_version="v1", kind="Pod", metadata=pod_metadata, spec=pod_spec)
        logger.info("[Deploy weblog] Weblog pod configuration done.")
        return pod_body

    def install_weblog_pod(self, namespace="default"):
        try:
            logger.info("[Deploy weblog] Installing weblog pod using admission controller")
            pod_body = self._get_base_weblog_pod()
            self.k8s_cluster_info.core_v1_api().create_namespaced_pod(namespace=namespace, body=pod_body)
            logger.info("[Deploy weblog] Weblog pod using admission controller created. Waiting for it to be ready!")
            self.wait_for_weblog_ready_by_label_app("my-app", namespace, timeout=200)
        except Exception as e:
            logger.error(f"[Deploy weblog] Error installing weblog pod: {e}")

    def install_weblog_pod_with_manual_inject(self, namespace="default"):
        """We do our own pod mutation to inject the library manually instead of using the admission controller"""
        try:
            pod_body = self._get_base_weblog_pod()
            pod_body.spec.init_containers = []
            init_container1 = client.V1Container(
                command=["sh", "copy-lib.sh", "/datadog-lib"],
                name="datadog-tracer-init",
                image=self.library_init_image,
                image_pull_policy="Always",
                termination_message_path="/dev/termination-log",
                termination_message_policy="File",
                volume_mounts=[client.V1VolumeMount(mount_path="/datadog-lib", name="datadog-auto-instrumentation")],
            )
            pod_body.spec.init_containers.append(init_container1)
            pod_body.spec.containers[0].env.append(client.V1EnvVar(name="DD_LOGS_INJECTION", value="true"))
            # Env vars for manual injection. Each library has its own env vars
            for lang_env_vars in K8sWeblog.manual_injection_props["js" if self.library == "nodejs" else self.library]:
                pod_body.spec.containers[0].env.append(
                    client.V1EnvVar(name=lang_env_vars["name"], value=lang_env_vars["value"])
                )
            # Env vars for UDS or network
            if self.dd_cluster_uds:
                pod_body.spec.containers[0].env.append(
                    client.V1EnvVar(name="DD_TRACE_AGENT_URL", value="unix:///var/run/datadog/apm.socket")
                )
            else:
                pod_body.spec.containers[0].env.append(
                    client.V1EnvVar(
                        name="DD_AGENT_HOST",
                        value_from=client.V1EnvVarSource(
                            field_ref=client.V1ObjectFieldSelector(field_path="status.hostIP")
                        ),
                    )
                )
            # Volume Mounts
            volume_mounts = []
            volume_mounts.append(client.V1VolumeMount(mount_path="/datadog-lib", name="datadog-auto-instrumentation"))
            if self.dd_cluster_uds:
                volume_mounts.append(client.V1VolumeMount(mount_path="/var/run/datadog", name="datadog"))
            pod_body.spec.containers[0].volume_mounts = volume_mounts

            # Volumes
            volumes = []
            volumes.append(
                client.V1Volume(name="datadog-auto-instrumentation", empty_dir=client.V1EmptyDirVolumeSource())
            )
            if self.dd_cluster_uds:
                volumes.append(
                    client.V1Volume(
                        name="datadog",
                        host_path=client.V1HostPathVolumeSource(path="/var/run/datadog", type="DirectoryOrCreate"),
                    )
                )
            pod_body.spec.volumes = volumes

            self.k8s_cluster_info.core_v1_api().create_namespaced_pod(namespace=namespace, body=pod_body)
            self.wait_for_weblog_ready_by_label_app("my-app", namespace, timeout=200)
        except Exception as e:
            logger.error(f"[Deploy weblog with manual inject] Error installing weblog pod: {e}")

    def wait_for_weblog_ready_by_label_app(self, app_name, namespace, timeout=60):
        logger.info(
            f"[Deploy weblog] Waiting for weblog to be ready(by label) .App {app_name}. Timeout {timeout} seconds."
        )
        pod_ready = False
        w = watch.Watch()
        for event in w.stream(
            func=self.list_namespaced_pod,
            namespace=namespace,
            label_selector=f"app={app_name}",
            timeout_seconds=timeout,
        ):
            if (
                "status" in event["object"]
                and event["object"]["status"]["phase"] == "Running"
                and event["object"]["status"]["containerStatuses"][0]["ready"]
            ):
                w.stop()
                logger.info("[Deploy weblog] Weblog started!")
                pod_ready = True
                break

        if not pod_ready:
            pod_status = self.k8s_cluster_info.core_v1_api().read_namespaced_pod_status(
                name="my-app", namespace=namespace
            )
            logger.error("[Deploy weblog] weblog not created. Last status: %s" % pod_status)
            pod_logs = self.k8s_cluster_info.core_v1_api().read_namespaced_pod_log(name="my-app", namespace=namespace)
            logger.error(f"[Deploy weblog] weblog logs: {pod_logs}")
            raise Exception("[Deploy weblog] Weblog not created")

    @retry(delay=1, tries=5)
    def list_namespaced_pod(self, namespace, **kwargs):
        """Necessary to retry the list_namespaced_pod call in case of error (used by watch stream)"""
        return self.k8s_cluster_info.core_v1_api().list_namespaced_pod(namespace, **kwargs)

    def export_debug_info(self, namespace="default"):
        """Extracts debug info from the k8s weblog app and logs it to the specified folder."""

        # check weblog describe pod
        try:
            api_response = self.k8s_cluster_info.core_v1_api().read_namespaced_pod("my-app", namespace=namespace)
            k8s_logger(self.output_folder, "myapp.describe").info(api_response)
        except Exception as e:
            k8s_logger(self.output_folder, "myapp.describe").info(
                "Exception when calling CoreV1Api->read_namespaced_pod: %s\n" % e
            )

        # check weblog logs for pod
        try:
            api_response = self.k8s_cluster_info.core_v1_api().read_namespaced_pod_log(
                name="my-app", namespace=namespace
            )
            k8s_logger(self.output_folder, "myapp.logs").info(api_response)
        except Exception as e:
            k8s_logger(self.output_folder, "myapp.logs").info(
                "Exception when calling CoreV1Api->read_namespaced_pod_log: %s\n" % e
            )

        app_name = f"{self.library}-app"
        try:
            pods = self.k8s_cluster_info.core_v1_api().list_namespaced_pod(
                namespace="default", label_selector=f"app={app_name}"
            )
            for index in range(len(pods.items)):
                k8s_logger(self.output_folder, "deployment.logs").info(
                    "-----------------------------------------------"
                )
                api_response = self.k8s_cluster_info.core_v1_api().read_namespaced_pod(pods.items[index].metadata.name)

                k8s_logger(self.output_folder, "deployment.logs").info(api_response)
                api_response = self.k8s_cluster_info.core_v1_api().read_namespaced_pod_log(
                    name=pods.items[index].metadata.name
                )
                k8s_logger(self.output_folder, "deployment.logs").info(api_response)
        except Exception as e:
            k8s_logger(self.output_folder, "deployment.logs").info("Exception when calling deployment data: %s\n" % e)
