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

        # pod_ready = False
        # for i in range(0, 10):
        #    try:

        #        pod_status = v1.read_namespaced_pod_status(name="my-app", namespace="default")
        #        if pod_status.status.phase == "Running":
        #            logger.info(f"Pod status weblog running!")
        #            pod_ready = True
        #            break
        #        else:
        #            time.sleep(5)
        #    except client.exceptions.ApiException as e:
        #        logger.info(f"Pod weblog status error: {e}")
        #        time.sleep(5)

        # if not pod_ready:
        #    logger.error("weblog not created. Last status: %s" % pod_status)
        #    pod_logs = v1.read_namespaced_pod_log(name="my-app", namespace="default")
        #    logger.error(f"weblog logs: {pod_logs}")
        #    raise Exception("Weblog not created")

        pod_ready = False
        w = watch.Watch()
        for event in w.stream(
            func=v1.list_namespaced_pod, namespace="default", label_selector="app=my-app", timeout_seconds=100
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

    def deploy_app_auto(self, app_image, library):
        v1 = client.CoreV1Api()
        deployment_name = f"test-{library}-deployment"

        deployment_metadata = client.V1ObjectMeta(
            name=deployment_name, namespace="default", labels={"app": f"{library}-app",},
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
            metadata=client.V1ObjectMeta(name=deployment_name, labels={"app": f"{library}-app"}),
            spec=client.V1PodSpec(containers=[container]),
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
        api = client.AppsV1Api()
        resp = api.create_namespaced_deployment(body=deployment, namespace="default")
        self._wait_for_deployment_complete(deployment_name, timeout=60)

        # deployment_ready = False
        # w = watch.Watch()
        # for event in w.stream(
        #    func=api.list_namespaced_deployment, namespace="default", label_selector=f"app={library}-app", timeout_seconds=60
        # ):
        #    if event["object"].status.phase == "Running":
        #        w.stop()
        #        logger.info("Weblog deployment started!")
        #        deployment_ready = True
        #        break

        # if not deployment_ready:

        #    deployment_status = api.read_namespaced_deployment_status(name=deployment_name, namespace='default')
        #    logger.error("weblog deployment not created. Last status: %s" % deployment_status)
        #    deployment_logs = api.read_namespaced_deployment(name=deployment_name, namespace="default")
        #    logger.error(f"weblog logs: {deployment_logs}")
        #    raise Exception("Weblog deplyment not created")

    # deploy-app-auto installs a target app for auto library injection testing.
    # It returns when the deployment is available and the rollout is finished.
    # function deploy-app-auto() {
    #    echo "[Deploy] deploy-app-auto: deploying app for library ${TEST_LIBRARY}"
    #    deployment_name=test-${TEST_LIBRARY}-deployment
    #    helm template lib-injection/common \
    #      -f "lib-injection/build/docker/$TEST_LIBRARY/values-override.yaml" \
    #      --set library="${TEST_LIBRARY}" \
    #      --set as_deployment="true" \
    #      --set deployment=${deployment_name} \
    #      --set test_app_image="${LIBRARY_INJECTION_TEST_APP_IMAGE}" \
    #       | kubectl apply -f -

    #   echo "[Deploy] deploy-app-auto: waiting for deployments/${deployment_name} available"
    #   kubectl rollout status deployments/${deployment_name} --timeout=5m
    #   kubectl wait deployments/${deployment_name} --for condition=Available=True --timeout=5m
    #   remove-terminating-pods
    #   kubectl get pods
    #
    #    echo "[Deploy] deploy-app-auto: done"
    # }

    def _wait_for_deployment_complete(self, deployment_name, timeout=60):
        v1 = client.CoreV1Api()
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
