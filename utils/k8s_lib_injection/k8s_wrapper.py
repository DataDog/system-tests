import time
from kubernetes import client, config, watch


def retry(max_retries, wait_time):
    """ Decorator to retry a function if it fails."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            if retries < max_retries:
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    retries += 1
                    time.sleep(wait_time)
            else:
                raise Exception(f"Max retries of function {func} exceeded")

        return wrapper

    return decorator


class K8sWrapper:
    """ Wrap methods from CoreV1Api and AppsV1Api to make it fail-safe.
    In a simple execution, the methods used here are usually smooth.
    Problems arise when we run tests with a lot of parallelism.
    We apply a retry policy """

    def __init__(self, k8s_kind_cluster):
        self.k8s_kind_cluster = k8s_kind_cluster

    @retry(max_retries=5, wait_time=1)
    def core_v1_api(self):
        return client.CoreV1Api(api_client=config.new_client_from_config(context=self.k8s_kind_cluster.context_name))

    @retry(max_retries=5, wait_time=1)
    def apps_api(self):
        return client.AppsV1Api(api_client=config.new_client_from_config(context=self.k8s_kind_cluster.context_name))

    @retry(max_retries=5, wait_time=1)
    def create_namespaced_daemon_set(self, namespace="default", body=None):
        self.apps_api().create_namespaced_daemon_set(namespace="default", body=body)

    @retry(max_retries=5, wait_time=1)
    def read_namespaced_daemon_set_status(self, name=None, namespace="default"):
        return self.apps_api().read_namespaced_daemon_set_status(name=name, namespace=namespace)

    @retry(max_retries=5, wait_time=1)
    def read_namespaced_daemon_set(self, name=None, namespace="default"):
        return self.apps_api().read_namespaced_daemon_set(name=name, namespace=namespace)

    @retry(max_retries=5, wait_time=1)
    def replace_namespaced_config_map(self, name=None, namespace="default", body=None):
        return self.core_v1_api().replace_namespaced_config_map(name=name, namespace=namespace, body=body)

    @retry(max_retries=5, wait_time=1)
    def create_namespaced_config_map(self, namespace="default", body=None):
        return self.core_v1_api().create_namespaced_config_map(namespace=namespace, body=body)

    @retry(max_retries=5, wait_time=1)
    def list_namespaced_config_map(self, namespace, **kwargs):
        return self.core_v1_api().list_namespaced_config_map(namespace, **kwargs)

    @retry(max_retries=5, wait_time=1)
    def list_namespaced_pod(self, namespace, **kwargs):
        return self.core_v1_api().list_namespaced_pod(namespace, **kwargs)

    @retry(max_retries=5, wait_time=1)
    def read_namespaced_pod(self, pod_name, namespace="default"):
        return self.core_v1_api().read_namespaced_pod(pod_name, namespace=namespace)

    @retry(max_retries=5, wait_time=1)
    def read_namespaced_pod_log(self, name=None, namespace="default"):
        return self.core_v1_api().read_namespaced_pod_log(name=name, namespace=namespace)

    @retry(max_retries=5, wait_time=1)
    def read_namespaced_pod_status(self, name=None, namespace="default"):
        return self.core_v1_api().read_namespaced_pod_status(name=name, namespace=namespace)

    @retry(max_retries=5, wait_time=1)
    def list_deployment_for_all_namespaces(self):
        return self.apps_api().list_deployment_for_all_namespaces()

    @retry(max_retries=5, wait_time=1)
    def create_namespaced_pod(self, namespace="default", body=None):
        return self.core_v1_api().create_namespaced_pod(namespace=namespace, body=body)

    @retry(max_retries=5, wait_time=1)
    def create_namespaced_deployment(self, body=None, namespace="default"):
        return self.apps_api().create_namespaced_deployment(namespace=namespace, body=body)

    @retry(max_retries=5, wait_time=1)
    def read_namespaced_deployment_status(self, deployment_name, namespace="default"):
        return self.apps_api().read_namespaced_deployment_status(deployment_name, namespace=namespace)

    @retry(max_retries=5, wait_time=1)
    def read_namespaced_deployment(self, deployment_name, namespace="default"):
        return self.apps_api().read_namespaced_deployment(deployment_name, namespace=namespace)

    @retry(max_retries=5, wait_time=1)
    def patch_namespaced_deployment(self, deployment_name, namespace, deploy_data):
        return self.apps_api().patch_namespaced_deployment(deployment_name, namespace, deploy_data)

    @retry(max_retries=5, wait_time=1)
    def delete_namespaced_pod(self, pod_name_running, namespace):
        return self.core_v1_api().delete_namespaced_pod(pod_name_running, namespace=namespace)
