import os
import time

import requests
from utils import scenarios, features, bug, context
from utils.tools import logger
from utils.onboarding.weblog_interface import make_get_request, warmup_weblog
from utils.onboarding.backend_interface import wait_backend_trace_id
from utils.onboarding.wait_for_tcp_port import wait_for_port
from utils import scenarios, features


class _TestAdmisionController:
    def test_inject_admission_controller(self, test_k8s_instance):
        logger.info(
            f"Launching test _test_inject_admission_controller: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_datadog_cluster_agent()
        test_k8s_instance.deploy_weblog_as_pod()
        traces_json = self._get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster.agent_port)
        assert len(traces_json) > 0, "No traces found"
        logger.info(f"Test _test_inject_admission_controller finished")

    def test_inject_uds_admission_controller(self, test_k8s_instance):
        logger.info(
            f"Launching test test_inject_uds_admission_controller: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_datadog_cluster_agent(use_uds=True)
        test_k8s_instance.deploy_weblog_as_pod()
        traces_json = self._get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster.agent_port)
        assert len(traces_json) > 0, "No traces found"
        logger.info(f"Test test_inject_uds_admission_controller finished")

    def test_inject_without_admission_controller(self, test_k8s_instance):
        logger.info(
            f"Launching test _test_inject_without_admission_controller: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_weblog_as_pod(with_admission_controller=False)
        traces_json = self._get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster.agent_port)
        assert len(traces_json) > 0, "No traces found"
        logger.info(f"Test _test_inject_without_admission_controller finished")

    def test_inject_uds_without_admission_controller(self, test_k8s_instance):
        logger.info(
            f"Launching test test_inject_uds_without_admission_controller: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_weblog_as_pod(with_admission_controller=False, use_uds=True)
        traces_json = self._get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster.agent_port)
        assert len(traces_json) > 0, "No traces found"
        logger.info(f"Test test_inject_uds_without_admission_controller finished")

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


@features.k8s_admission_controller
@scenarios.k8s_library_injection_asm
class TestAdmisionControllerAsm:
    """Test ASM features activation with admission controller."""

    def test_inject_asm_admission_controller(self, test_k8s_instance):
        logger.info(
            f"Launching test test_inject_asm_admission_controller: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )

        asm_features = {
            "datadog.asm.iast.enabled": "true",
            "datadog.asm.sca.enabled": "true",
            "datadog.asm.threats.enabled": "true",
        }
        test_k8s_instance.deploy_datadog_cluster_agent(features=asm_features)
        test_k8s_instance.deploy_agent()

        weblog_port = test_k8s_instance.k8s_kind_cluster.weblog_port
        logger.info(f"Waiting for weblog available [localhost:{weblog_port}]")
        wait_for_port(weblog_port, "localhost", 80.0)
        logger.info(f"[localhost:{weblog_port}]: Weblog app is ready!")
        warmup_weblog(f"http://localhost:{weblog_port}/")
        logger.info(f"Making a request to weblog [localhost:{weblog_port}]")
        request_uuid = make_get_request(f"http://localhost:{weblog_port}/")

        logger.info(f"Http request done with uuid: [{request_uuid}] for [localhost:{weblog_port}]")
        wait_backend_trace_id(request_uuid, 120.0, profile=False, validator=backend_trace_validator)


@features.k8s_admission_controller
@scenarios.k8s_library_injection_profiling
class TestAdmisionControllerProfiling:
    """Test profiling activation with the admission controller."""

    def _check_profiling_request_sent(self, agent_port, timeout=90):
        """ Use test agent profiling endpoint to check if the profiling data has been sent by the injectect library. 
        Checks the request made to the profiling endpoint (/profiling/v1/input).
        The profiling post data can take between 12 and 90 seconds (12 if the library supports both env vars, 90 if it supports neither. """
        mustend = time.time() + timeout
        while time.time() < mustend:
            response = requests.get(f"http://localhost:{agent_port}/test/session/requests")
            for request in response.json():
                if request["url"].endswith("/profiling/v1/input"):
                    return True
            time.sleep(1)
        return False

    def test_profiling_disabled_by_default(self, test_k8s_instance):
        logger.info(f"Launching test test_profiling_disabled_by_default")
        logger.info(
            f": Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_datadog_cluster_agent()
        # if profiling is enabled force some profiling data to be sent
        test_k8s_instance.deploy_weblog_as_pod(
            env={"DD_PROFILING_UPLOAD_PERIOD": "10", "DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD": "1500"}
        )
        profiling_request_found = self._check_profiling_request_sent(test_k8s_instance.k8s_kind_cluster.agent_port)
        assert not profiling_request_found, "Profiling should be disabled by default, but a profiling request was found"

    @bug(context.library > "python@2.12.2", reason="APMON-1496")
    def test_profiling_admission_controller(self, test_k8s_instance):
        logger.info(f"Launching test test_profiling_admission_controller")
        logger.info(
            f": Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_datadog_cluster_agent(features={"datadog.profiling.enabled": "auto"})
        test_k8s_instance.deploy_weblog_as_pod(
            env={"DD_PROFILING_UPLOAD_PERIOD": "10", "DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD": "1500"}
        )
        profiling_request_found = self._check_profiling_request_sent(test_k8s_instance.k8s_kind_cluster.agent_port)
        assert profiling_request_found, "No profiling request found"

    @bug(context.library > "python@2.12.2", reason="APMON-1496")
    def test_profiling_override_cluster_env(self, test_k8s_instance):
        logger.info(f"Launching test test_profiling_override_cluster_env")
        logger.info(
            f": Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )
        cluster_agent_config = {
            "clusterAgent.env[0].name": "DD_ADMISSION_CONTROLLER_AUTO_INSTRUMENTATION_PROFILING_ENABLED",
            "clusterAgent.env[0].value": "auto",
        }
        test_k8s_instance.deploy_test_agent()
        test_k8s_instance.deploy_datadog_cluster_agent(features=cluster_agent_config)
        test_k8s_instance.deploy_weblog_as_pod(
            env={"DD_PROFILING_UPLOAD_PERIOD": "10", "DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD": "1500"}
        )
        profiling_request_found = self._check_profiling_request_sent(test_k8s_instance.k8s_kind_cluster.agent_port)
        assert profiling_request_found, "No profiling request found"

    def _test_inject_profiling_admission_controller_real(self, test_k8s_instance):
        logger.info(
            f"Launching test test_inject_profiling_admission_controller: Weblog: [{test_k8s_instance.k8s_kind_cluster.weblog_port}] Agent: [{test_k8s_instance.k8s_kind_cluster.agent_port}]"
        )

        test_k8s_instance.deploy_datadog_cluster_agent(features={"datadog.profiling.enabled": "auto"})
        test_k8s_instance.deploy_agent()
        test_k8s_instance.deploy_weblog_as_pod(
            env={"DD_PROFILING_UPLOAD_PERIOD": "10", "DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD": "1500"}
        )
        weblog_port = test_k8s_instance.k8s_kind_cluster.weblog_port
        logger.info(f"Waiting for weblog available [localhost:{weblog_port}]")
        wait_for_port(weblog_port, "localhost", 80.0)
        logger.info(f"[localhost:{weblog_port}]: Weblog app is ready!")
        warmup_weblog(f"http://localhost:{weblog_port}/")
        logger.info(f"Making a request to weblog [localhost:{weblog_port}]")
        request_uuid = make_get_request(f"http://localhost:{weblog_port}/")

        logger.info(f"Http request done with uuid: [{request_uuid}] for [localhost:{weblog_port}]")
        wait_backend_trace_id(request_uuid, 120.0, profile=True)


def backend_trace_validator(trace_id, trace_data):
    logger.info("Appsec trace validator")
    root_id = trace_data["trace"]["root_id"]
    if trace_data["trace"]["spans"][root_id]["metrics"]["_dd.appsec.enabled"] == 1.0:
        return True
    return False


@features.k8s_admission_controller
@scenarios.k8s_library_injection_basic
class TestAdmisionControllerBasic(_TestAdmisionController):
    pass
