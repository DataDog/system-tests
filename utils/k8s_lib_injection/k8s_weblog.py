import time
from kubernetes import client, watch
from utils.tools import logger


class K8sWeblog:
    def deploy_app_manual(self, app_image, library, library_init_image):
        logger.info(
            "[Deploy weblog] Deploying weblog as pod. weblog_variant_image: [%s], library: [%s], library_init_image: [%s]"
            % (app_image, library, library_init_image)
        )
        v1 = client.CoreV1Api()
        apps_api = client.AppsV1Api()

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

        pod_ready = False
        for i in range(0, 10):
            try:

                pod_status = v1.read_namespaced_pod_status(name="my-app", namespace="default")
                if pod_status.status.phase == "Running":
                    logger.info(f"Pod status weblog running!")
                    pod_ready = True
                    break
                else:
                    time.sleep(5)
            except client.exceptions.ApiException as e:
                logger.info(f"Pod weblog status error: {e}")
                time.sleep(5)

        if not pod_ready:
            logger.error("weblog not created. Last status: %s" % pod_status)
            pod_logs = v1.read_namespaced_pod_log(name="my-app", namespace="default")
            logger.error(f"weblog logs: {pod_logs}")
            raise Exception("Weblog not created")

        w = watch.Watch()
        for event in w.stream(
            func=v1.list_namespaced_pod, namespace="default", label_selector="app=my-app", timeout_seconds=60
        ):
            if event["object"].status.phase == "Running":
                w.stop()
                end_time = time.time()
                logger.info("Weblog started!")
                break
