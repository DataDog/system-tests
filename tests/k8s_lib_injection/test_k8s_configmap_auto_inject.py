import os
import time
import json
import requests
from utils import scenarios, features
from utils.tools import logger
from utils import scenarios, context, features
from kubernetes import client, config, watch
from utils import irrelevant


@features.k8s_admission_controller
@scenarios.k8s_library_injection_full
class TestConfigMapAutoInject:
    """ Datadog Agent Auto-injection tests using ConfigMap
        Check: https://datadoghq.atlassian.net/wiki/spaces/AO/pages/2983035648/Cluster+Agent+Development
    """

    def _get_dev_agent_traces(self, agent_port, retry=10):
        for _ in range(retry):
            logger.info(f"[Check traces] Checking traces:")
            response = requests.get(f"http://localhost:{agent_port}/test/traces")
            traces_json = response.json()
            if len(traces_json) > 0:
                logger.debug(f"Test traces response: {traces_json}")
                return traces_json
            time.sleep(2)
        return []

    def _get_default_auto_inject_config(self, test_k8s_instance, rc_rev=0):
        return [
            {
                "id": "11777398274940883092",
                "revision": rc_rev,
                "schema_version": "v1.0.0",
                "action": "enable",
                "lib_config": {
                    "library_language": f"{test_k8s_instance.library}",
                    "library_version": f"{test_k8s_instance.library_init_image_tag}",
                    "service_name": f"test-{test_k8s_instance.library}-service",
                    "env": "dev",
                    "tracing_enabled": True,
                    "tracing_sampling_rate": 0.90,
                },
                "k8s_target": {
                    "cluster": test_k8s_instance.k8s_kind_cluster.cluster_name,
                    "kind": "deployment",
                    "name": f"test-{test_k8s_instance.library}-deployment",
                    "namespace": "default",
                },
            }
        ]

    def _get_default_auto_inject_config_all_libraries(self, test_k8s_instance, rc_rev=0):
        """ Returns a list of config objects for all supported libraries. """
        return [
            {
                "id": "11777398274940883092",
                "revision": 0,
                "schema_version": "v1.0.0",
                "action": "enable",
                "lib_config": {
                    "library_language": "all",
                    "library_version": f"{test_k8s_instance.library_init_image_tag}",
                    "service_name": "test-service",
                    "env": "dev",
                    "tracing_enabled": True,
                    "tracing_sampling_rate": 0.90,
                },
                "k8s_target": {
                    "cluster": test_k8s_instance.k8s_kind_cluster.cluster_name,
                    "kind": "deployment",
                    "name": "test-python-deployment",
                    "namespace": "default",
                },
            },
            {
                "id": "11777398274940883092",
                "revision": 0,
                "schema_version": "v1.0.0",
                "action": "enable",
                "lib_config": {
                    "library_language": "all",
                    "library_version": f"{test_k8s_instance.library_init_image_tag}",
                    "service_name": "test-service",
                    "env": "dev",
                    "tracing_enabled": True,
                    "tracing_sampling_rate": 0.90,
                },
                "k8s_target": {
                    "cluster": test_k8s_instance.k8s_kind_cluster.cluster_name,
                    "kind": "deployment",
                    "name": "test-java-deployment",
                    "namespace": "default",
                },
            },
            {
                "id": "11777398274940883092",
                "revision": 0,
                "schema_version": "v1.0.0",
                "action": "enable",
                "lib_config": {
                    "library_language": "all",
                    "library_version": f"{test_k8s_instance.library_init_image_tag}",
                    "service_name": "test-service",
                    "env": "dev",
                    "tracing_enabled": True,
                    "tracing_sampling_rate": 0.90,
                },
                "k8s_target": {
                    "cluster": test_k8s_instance.k8s_kind_cluster.cluster_name,
                    "kind": "deployment",
                    "name": "test-js-deployment",
                    "namespace": "default",
                },
            },
            {
                "id": "11777398274940883092",
                "revision": 0,
                "schema_version": "v1.0.0",
                "action": "enable",
                "lib_config": {
                    "library_language": "all",
                    "library_version": f"{test_k8s_instance.library_init_image_tag}",
                    "service_name": "test-service",
                    "env": "dev",
                    "tracing_enabled": True,
                    "tracing_sampling_rate": 0.90,
                },
                "k8s_target": {
                    "cluster": test_k8s_instance.k8s_kind_cluster.cluster_name,
                    "kind": "deployment",
                    "name": "test-ruby-deployment",
                    "namespace": "default",
                },
            },
            {
                "id": "11777398274940883092",
                "revision": 0,
                "schema_version": "v1.0.0",
                "action": "enable",
                "lib_config": {
                    "library_language": "all",
                    "library_version": f"{test_k8s_instance.library_init_image_tag}",
                    "service_name": "test-service",
                    "env": "dev",
                    "tracing_enabled": True,
                    "tracing_sampling_rate": 0.90,
                },
                "k8s_target": {
                    "cluster": test_k8s_instance.k8s_kind_cluster.cluster_name,
                    "kind": "deployment",
                    "name": "test-dotnet-deployment",
                    "namespace": "default",
                },
            },
        ]

    def _check_for_env_vars(self, test_k8s_instance, expected_env_vars):
        """ evaluates whether the expected tracer config is reflected in the env vars of the targeted pod. """
        app_name = f"{test_k8s_instance.library}-app"
        pods = test_k8s_instance.k8s_wrapper.list_namespaced_pod("default", label_selector=f"app={app_name}")
        assert len(pods.items) != 0, f"No pods found for app {app_name}"

        for expected_env_var in expected_env_vars:
            env_var_found = False
            for env_var in pods.items[0].spec.containers[0].env:
                if env_var.name == expected_env_var["name"]:
                    assert (
                        env_var.value == expected_env_var["value"]
                    ), f"Env var {expected_env_var['name']} is not set to {expected_env_var['value']}"
                    env_var_found = True
                    break
            assert env_var_found, f"Env var {expected_env_var['name']} not found"

    def _check_for_pod_metadata(self, test_k8s_instance):
        """evaluates whether the expected admission labels and annotations are applied to the targeted pod."""
        library_version = test_k8s_instance.library_init_image_tag
        app_name = f"{test_k8s_instance.library}-app"
        pods = test_k8s_instance.k8s_wrapper.list_namespaced_pod("default", label_selector=f"app={app_name}")
        assert len(pods.items) != 0, f"No pods found for app {app_name}"

        assert (
            pods.items[0].metadata.labels["admission.datadoghq.com/enabled"] == "true"
        ), "annotation 'admission.datadoghq.com/enabled' wasn't 'true'"
        assert (
            pods.items[0].metadata.annotations[f"admission.datadoghq.com/{test_k8s_instance.library}-lib.version"]
            == f"{library_version}"
        ), f"annotation 'admission.datadoghq.com/{test_k8s_instance.library}-lib.version' wasn't '{library_version}'"
        assert (
            f"admission.datadoghq.com/{test_k8s_instance.library}-lib.version" in pods.items[0].metadata.annotations
        ), f"annotation 'admission.datadoghq.com/{test_k8s_instance.library}-lib.version' not found"

    def _check_for_pod_metadata_all_libraries(self, test_k8s_instance):
        """evaluates whether the expected admission labels and annotations are applied to the targeted pod."""
        library_version = test_k8s_instance.library_init_image_tag
        app_name = f"{test_k8s_instance.library}-app"
        pods = test_k8s_instance.k8s_wrapper.list_namespaced_pod("default", label_selector=f"app={app_name}")
        assert len(pods.items) == 1, f"No pods found for app {app_name}"

        assert (
            pods.items[0].metadata.labels["admission.datadoghq.com/enabled"] == "true"
        ), "annotation 'admission.datadoghq.com/enabled' wasn't 'true'"
        assert (
            pods.items[0].metadata.annotations[f"admission.datadoghq.com/all-lib.version"] == f"{library_version}"
        ), f"annotation 'admission.datadoghq.com/all-lib.version' wasn't 'all'"
        assert (
            f"admission.datadoghq.com/all-lib.version" in pods.items[0].metadata.annotations
        ), f"annotation 'admission.datadoghq.com/all-lib.version' not found"

    def _check_for_deploy_metadata(self, test_k8s_instance, rc_rev="0"):
        """evaluates whether the expected admission annotations are applied to the targeted deployment."""

        deployment_name = f"test-{test_k8s_instance.library}-deployment"
        rc_id = "11777398274940883092"
        deployment = test_k8s_instance.k8s_wrapper.read_namespaced_deployment(deployment_name)
        assert (
            deployment.metadata.annotations["admission.datadoghq.com/rc.id"] == rc_id
        ), f"Deployment annotation 'admission.datadoghq.com/rc.id' not equal [{rc_id}]. Deployment description: {deployment}"
        assert (
            deployment.metadata.annotations["admission.datadoghq.com/rc.rev"] == rc_rev
        ), f"Deployment annotation 'admission.datadoghq.com/rc.rev' not equal [{rc_rev}]. Deployment description: {deployment}"

    def _trigger_app_rolling_update(self, test_k8s_instance):
        """Starts a rolling update of the target deployment by injecting an environment variable.
          It returns when the deployment is available and the rollout is finished. 
        """
        deployment_name = f"test-{test_k8s_instance.library}-deployment"
        deploy_data = test_k8s_instance.k8s_wrapper.read_namespaced_deployment(deployment_name)
        # get envs from deployment's first container
        dep_envs = deploy_data.spec.template.spec.containers[0].env
        dep_envs.append(client.V1EnvVar(name="ENV_FOO", value="ENV_BAR"))
        deploy_data.spec.template.spec.containers[0].env = dep_envs
        test_k8s_instance.k8s_wrapper.patch_namespaced_deployment(deployment_name, "default", deploy_data)
        time.sleep(30)
        test_k8s_instance.test_weblog.wait_for_weblog_after_apply_configmap(f"{test_k8s_instance.library}-app")

    def _check_for_no_pod_metadata(self, test_k8s_instance):
        """ Ensures the targeted pod doesn't have admission labels. """
        app_name = f"{test_k8s_instance.library}-app"
        pods = test_k8s_instance.k8s_wrapper.list_namespaced_pod("default", label_selector=f"app={app_name}")
        assert len(pods.items) != 0, f"No pods found for app {app_name}"

        assert (
            "admission.datadoghq.com/enabled" not in pods.items[0].metadata.labels
        ), "annotation 'admission.datadoghq.com/enabled' is present but it shouldn't be there"

    def _check_for_disabled_pod_metadata(self, test_k8s_instance):
        """ Ensures the targeted pod doesn't have admission labels. """

        app_name = f"{test_k8s_instance.library}-app"
        pods = test_k8s_instance.k8s_wrapper.list_namespaced_pod("default", label_selector=f"app={app_name}")
        assert len(pods.items) != 0, f"No pods found for app {app_name}"
        assert (
            pods.items[0].metadata.labels["admission.datadoghq.com/enabled"] == "false"
        ), "annotation 'admission.datadoghq.com/enabled' wasn't 'false'"

    def test_fileprovider_configmap_case1(self, test_k8s_instance):
        """ Nominal case:
           - deploy app & agent
           - apply config
           - check for traces """

        logger.info(
            f"Launching test test_fileprovider_configmap_case1: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )
        test_k8s_instance.deploy_weblog_as_deployment()
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_operator_auto()
        default_config_data = self._get_default_auto_inject_config(test_k8s_instance)

        expected_env_vars = [{"name": "DD_TRACE_SAMPLE_RATE", "value": "0.90"}]

        test_k8s_instance.apply_config_auto_inject(json.dumps(default_config_data))
        traces_json = self._get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster.agent_port)

        logger.debug(f"Traces: {traces_json}")
        assert len(traces_json) > 0, "No traces found"

        self._check_for_env_vars(test_k8s_instance, expected_env_vars)
        self._check_for_pod_metadata(test_k8s_instance)
        self._check_for_deploy_metadata(test_k8s_instance)

        logger.info(f"Test test_fileprovider_configmap_case1 finished")

    def test_fileprovider_configmap_case2(self, test_k8s_instance):
        """ Config change:
               - deploy app & agent
               - apply config
               - check for traces
               - apply different tracers config
               - check for traces """

        logger.info(
            f"Launching test test_fileprovider_configmap_case2: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )

        test_k8s_instance.deploy_weblog_as_deployment()
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_operator_auto()
        default_config_data = self._get_default_auto_inject_config(test_k8s_instance, rc_rev=1)

        default_config_data[0]["lib_config"]["tracing_sampling_rate"] = 0.50
        expected_env_vars = [{"name": "DD_TRACE_SAMPLE_RATE", "value": "0.50"}]

        test_k8s_instance.apply_config_auto_inject(json.dumps(default_config_data), rev=1)
        traces_json = self._get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster.agent_port)

        logger.debug(f"Traces: {traces_json}")
        assert len(traces_json) > 0, "No traces found"

        self._check_for_env_vars(test_k8s_instance, expected_env_vars)
        self._check_for_pod_metadata(test_k8s_instance)
        self._check_for_deploy_metadata(test_k8s_instance, rc_rev="1")

        logger.info(f"Test test_fileprovider_configmap_case2 finished")

    def test_fileprovider_configmap_case3(self, test_k8s_instance):
        """  Config persistence:
               - deploy app & agent
               - apply config
               - check for traces
               - trigger unrelated rolling-update
               - check for traces
         """
        logger.info(
            f"Launching test test_fileprovider_configmap_case3: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )
        test_k8s_instance.deploy_weblog_as_deployment()
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_operator_auto()
        default_config_data = self._get_default_auto_inject_config(test_k8s_instance)

        expected_env_vars = [{"name": "DD_TRACE_SAMPLE_RATE", "value": "0.90"}]

        test_k8s_instance.apply_config_auto_inject(json.dumps(default_config_data))
        traces_json = self._get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster.agent_port)

        logger.debug(f"Traces: {traces_json}")
        assert len(traces_json) > 0, "No traces found"

        self._check_for_env_vars(test_k8s_instance, expected_env_vars)
        self._check_for_pod_metadata(test_k8s_instance)
        self._check_for_deploy_metadata(test_k8s_instance)

        logger.debug(" Trigger unrelated rolling-update")
        self._trigger_app_rolling_update(test_k8s_instance)

        logger.debug(f"Running tests after trigger unrelated rolling-update")
        traces_json = self._get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster.agent_port)
        logger.debug(f"Traces: {traces_json}")
        assert len(traces_json) > 0, "No traces found after trigger unrelated rolling-update"

        self._check_for_env_vars(test_k8s_instance, expected_env_vars)
        self._check_for_pod_metadata(test_k8s_instance)
        self._check_for_deploy_metadata(test_k8s_instance)

        logger.info(f"Test test_fileprovider_configmap_case3 finished")

    def test_fileprovider_configmap_case4(self, test_k8s_instance):
        """  Mismatching config:
               - deploy app & agent
               - apply config with non-matching cluster name
               - check that metadata does not exist """

        logger.info(
            f"Launching test test_fileprovider_configmap_case4: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )
        test_k8s_instance.deploy_weblog_as_deployment()
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_operator_auto()
        default_config_data = self._get_default_auto_inject_config(test_k8s_instance)
        default_config_data[0]["k8s_target"]["cluster"] = "lib-injection-testing-no-match"
        try:
            test_k8s_instance.apply_config_auto_inject(json.dumps(default_config_data))
        except TimeoutError as e:
            pass  # DD agent cluster will not read this config map becausr the cluster name is not matching.
        self._check_for_no_pod_metadata(test_k8s_instance)

        logger.info(f"Test test_fileprovider_configmap_case4 finished")

    def test_fileprovider_configmap_case5(self, test_k8s_instance):
        """ Config change to action:disable
                - deploy app & agent
                - apply matching config
                - check that deployment instrumented
                - apply config with action:disable
                - check that deployment is not longer instrumented
       """
        logger.info(
            f"Launching test test_fileprovider_configmap_case5: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )
        test_k8s_instance.deploy_weblog_as_deployment()
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_operator_auto()
        default_config_data = self._get_default_auto_inject_config(test_k8s_instance)

        test_k8s_instance.apply_config_auto_inject(json.dumps(default_config_data))
        traces_json = self._get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster.agent_port)
        logger.debug(f"Traces: {traces_json}")
        assert len(traces_json) > 0, "No traces found"

        logger.debug("Apply disabled config")
        default_config_data = self._get_default_auto_inject_config(test_k8s_instance, rc_rev=2)
        default_config_data[0]["action"] = "disable"
        test_k8s_instance.apply_config_auto_inject(json.dumps(default_config_data), rev=2)
        self._check_for_disabled_pod_metadata(test_k8s_instance)
        logger.info(f"Test _test_fileprovider_configmap_case5 finished")

    @irrelevant(
        condition=not hasattr(context.scenario, "_library_init_image_tag")
        or context.scenario._library_init_image_tag != "",
        reason="Test a discontinued feature",
    )
    def test_fileprovider_configmap_case6(self, test_k8s_instance):
        """  Inject-all case (for batch instrumentation)
           - use language name "all" in RC config
           - all supported language libraries should be injected into the container
           - ensure traces are produced and the pods are modified correctly 
        """
        logger.info(
            f"Launching test test_fileprovider_configmap_case6: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )

        test_k8s_instance.deploy_weblog_as_deployment()
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_operator_auto()

        expected_env_vars = [{"name": "DD_TRACE_SAMPLE_RATE", "value": "0.90"}]

        all_config_data = self._get_default_auto_inject_config_all_libraries(test_k8s_instance)
        test_k8s_instance.apply_config_auto_inject(json.dumps(all_config_data), timeout=300)

        traces_json = self._get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster.agent_port)
        logger.debug(f"Traces: {traces_json}")
        assert len(traces_json) > 0, "No traces found"

        self._check_for_env_vars(test_k8s_instance, expected_env_vars)
        self._check_for_pod_metadata_all_libraries(test_k8s_instance)
        self._check_for_deploy_metadata(test_k8s_instance)

        logger.info(f"Test test_fileprovider_configmap_case6 finished")
