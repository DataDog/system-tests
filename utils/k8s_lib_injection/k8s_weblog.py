import time, datetime
from kubernetes import client, watch
from utils.tools import logger


class K8sWeblog:
    def deploy_app_manual(self, app_image, library, library_init_image):
        """ Installs a target app for manual library injection testing.
            It returns when the app pod is ready."""

        v1 = client.CoreV1Api()
        logger.info(
            "[Deploy weblog] Deploying weblog as pod. weblog_variant_image: [%s], library: [%s], library_init_image: [%s]"
            % (app_image, library, library_init_image)
        )

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
            annotations={f"admission.datadoghq.com/{library}-lib.custom-image": f"{library_init_image}"},
        )

        containers = []
        container1 = client.V1Container(
            name="my-app",
            image=app_image,
            env=[
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
                        field_ref=client.V1ObjectFieldSelector(
                            field_path="metadata.labels['tags.datadoghq.com/service']"
                        )
                    ),
                ),
                client.V1EnvVar(
                    name="DD_VERSION",
                    value_from=client.V1EnvVarSource(
                        field_ref=client.V1ObjectFieldSelector(
                            field_path="metadata.labels['tags.datadoghq.com/version']"
                        )
                    ),
                ),
                client.V1EnvVar(name="DD_TRACE_DEBUG", value="1"),
            ],
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

        pod_spec = client.V1PodSpec(containers=containers)

        pod_body = client.V1Pod(api_version="v1", kind="Pod", metadata=pod_metadata, spec=pod_spec)

        v1.create_namespaced_pod(namespace="default", body=pod_body)
        self.wait_for_weblog_ready_by_label_app("my-app", timeout=100)

    def deploy_app_auto(self, app_image, library):
        """ Installs a target app for auto library injection testing.
            It returns when the deployment is available and the rollout is finished."""
        api = client.AppsV1Api()
        deployment_name = f"test-{library}-deployment"

        deployment_metadata = client.V1ObjectMeta(
            name=deployment_name, namespace="default", labels={"app": f"{library}-app"},
        )

        # Configureate Pod template container
        container = client.V1Container(
            name=f"{library}-app",
            image=app_image,
            env=[client.V1EnvVar(name="SERVER_PORT", value="18080"),],
            readiness_probe=client.V1Probe(
                timeout_seconds=5,
                success_threshold=3,
                failure_threshold=10,
                http_get=client.V1HTTPGetAction(path="/", port=18080),
                initial_delay_seconds=20,
                period_seconds=10,
            ),
            ports=[client.V1ContainerPort(container_port=18080, host_port=18080, name="http", protocol="TCP")],
        )

        # Create and configure a spec section
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": f"{library}-app"}),
            spec=client.V1PodSpec(containers=[container], restart_policy="Always"),
        )

        # Create the specification of deployment
        spec = client.V1DeploymentSpec(
            replicas=1, template=template, selector={"matchLabels": {"app": f"{library}-app"}}
        )

        # Instantiate the deployment object
        deployment = client.V1Deployment(
            api_version="apps/v1", kind="Deployment", metadata=deployment_metadata, spec=spec,
        )
        # Create deployment
        resp = api.create_namespaced_deployment(body=deployment, namespace="default")
        self._wait_for_deployment_complete(deployment_name, timeout=100)

    def wait_for_weblog_after_apply_configmap(self, app_name, timeout=200):
        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace="default", label_selector=f"app={app_name}")
        logger.info(f"[Weblog] Currently running pods [{app_name}]:[{len(pods.items)}]")
        if len(pods.items) == 2:
            if pods.items[0].status.phase == "Pending" or pods.items[1].status.phase == "Pending":
                pod_name_pending = (
                    pods.items[0].metadata.name
                    if pods.items[0].status.phase == "Pending"
                    else pods.items[1].metadata.name
                )
                pod_name_running = (
                    pods.items[0].metadata.name
                    if pods.items[0].status.phase == "Running"
                    else pods.items[1].metadata.name
                )

                logger.info(f"[Weblog] Deleting previous pod {pod_name_running}")
                v1.delete_namespaced_pod(pod_name_running, "default")
                logger.info(f"[Weblog] Waiting for pod {pod_name_pending} to be running")
                self.wait_for_weblog_ready_by_pod_name(pod_name_pending, timeout=timeout)

    def wait_for_weblog_ready_by_label_app(self, app_name, timeout=60):
        v1 = client.CoreV1Api()
        pod_ready = False
        w = watch.Watch()
        for event in w.stream(
            func=v1.list_namespaced_pod, namespace="default", label_selector=f"app={app_name}", timeout_seconds=timeout
        ):
            if event["object"].status.phase == "Running" and event["object"].status.container_statuses[0].ready:
                w.stop()
                logger.info("Weblog started!")
                pod_ready = True
                break

        if not pod_ready:
            pod_status = v1.read_namespaced_pod_status(name="my-app", namespace="default")
            logger.error("weblog not created. Last status: %s" % pod_status)
            pod_logs = v1.read_namespaced_pod_log(name="my-app", namespace="default")
            logger.error(f"weblog logs: {pod_logs}")
            raise Exception("Weblog not created")

    def wait_for_weblog_ready_by_pod_name(self, pod_name, timeout=60):
        v1 = client.CoreV1Api()
        start = datetime.datetime.now()
        while True:
            pod = v1.read_namespaced_pod(pod_name, "default")
            if pod.status.phase == "Running" and pod.status.container_statuses[0].ready:
                return
            time.sleep(1)
            now = datetime.datetime.now()
            if (now - start).seconds > timeout:
                raise Exception(f"Pod {pod_name} did not start in {timeout} seconds")

    def _wait_for_deployment_complete(self, deployment_name, timeout=60):
        api = client.AppsV1Api()
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(2)
            response = api.read_namespaced_deployment_status(deployment_name, "default")
            s = response.status
            if (
                s.updated_replicas == response.spec.replicas
                and s.replicas == response.spec.replicas
                and s.available_replicas == response.spec.replicas
                and s.observed_generation >= response.metadata.generation
            ):
                return True
            else:
                logger.info(
                    f"[updated_replicas:{s.updated_replicas},replicas:{s.replicas}"
                    ",available_replicas:{s.available_replicas},observed_generation:{s.observed_generation}] waiting..."
                )

        raise RuntimeError(f"Waiting timeout for deployment {deployment_name}")
