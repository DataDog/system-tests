import os

import pytest

from utils import scenarios, context, features
from utils.tools import logger
from utils.onboarding.weblog_interface import make_get_request
from utils.onboarding.backend_interface import wait_backend_trace_id
from utils.onboarding.wait_for_tcp_port import wait_for_port


class _OnboardingInstallBaseTest:
    def test_for_traces(self, onboardig_vm):
        """ We can easily install agent and lib injection software from agent installation script. Given a  sample application we can enable tracing using local environment variables.  
            After starting application we can see application HTTP requests traces in the backend.
            Using the agent installation script we can install different versions of the software (release or beta) in different OS."""

        logger.info(f"Launching test for : [{onboardig_vm.ip}]")
        logger.info(f"Waiting for weblog available [{onboardig_vm.ip}]")
        # TODO move this wait command to the scenario warmup. How to do this? Pulumi is working in parallel and async, in the scenario warmup we don't have the server IP
        wait_for_port(5985, onboardig_vm.ip, 80.0)
        logger.info(f"[{onboardig_vm.ip}]: Weblog app is ready!")
        logger.info(f"Making a request to weblog [{onboardig_vm.ip}]")
        request_uuid = make_get_request("http://" + onboardig_vm.ip + ":5985/")
        logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{onboardig_vm.ip}]")
        wait_backend_trace_id(request_uuid, 60.0)


class _OnboardingUninstallBaseTest:
    def test_no_traces_after_uninstall(self, onboardig_vm):
        logger.info(f"Launching uninstallation test for : [{onboardig_vm.ip}]")
        logger.info(f"Waiting for weblog available [{onboardig_vm.ip}]")
        # We uninstalled the autoinjection software, but the application should work
        wait_for_port(5985, onboardig_vm.ip, 60.0)
        logger.info(f"Making a request to weblog [{onboardig_vm.ip}]")
        request_uuid = make_get_request("http://" + onboardig_vm.ip + ":5985/")
        logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{onboardig_vm.ip}]")
        try:
            wait_backend_trace_id(request_uuid, 10.0)
            raise AssertionError("The weblog application is instrumented after uninstall DD software")
        except TimeoutError:
            # OK there are no traces, the weblog app is not instrumented
            pass


@features.container_auto_instrumentation
@scenarios.onboarding_container_install_manual
class TestOnboardingInstallManualContainer(_OnboardingInstallBaseTest):
    pass


@features.host_auto_instrumentation
@scenarios.onboarding_host_install_manual
class TestOnboardingInstallManualHost(_OnboardingInstallBaseTest):
    pass


@features.host_auto_instrumentation
@scenarios.onboarding_host_install_script
class TestOnboardingInstallScriptHost(_OnboardingInstallBaseTest):
    pass


@features.container_auto_instrumentation
@scenarios.onboarding_container_install_script
class TestOnboardingInstallScriptContainer(_OnboardingInstallBaseTest):
    pass


#########################
# Uninstall scenarios
#########################


@features.container_auto_instrumentation
@scenarios.onboarding_container_uninstall
class TestOnboardingUninstallContainer(_OnboardingUninstallBaseTest):
    pass


@features.host_auto_instrumentation
@scenarios.onboarding_host_uninstall
class TestOnboardingUninstallHost(_OnboardingUninstallBaseTest):
    pass
