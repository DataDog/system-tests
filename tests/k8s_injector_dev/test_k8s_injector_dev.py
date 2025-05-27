from utils import scenarios, features, logger
from utils.injector_dev.harness import Harness


@features.k8s_admission_controller
@scenarios.k8s_injector_dev_single_service
class TestK8sLibInjection:
    """Test K8s injector dev tool"""

    def test_k8s_injector_dev(self):
        logger.info("Testing K8s lib injection using the injector-dev tool")
        # Initialize the harness with Must(New(t))
        h = Harness.must(Harness.new("single-service.yaml"))

        # Test the python-injection deployment
        injected = h.deployment("python-injection", "application")
        h.require(injected.has_injection())
        h.require(injected.has_env("DD_PROFILING_ENABLED", "true"))

        # Test the python-no-injection deployment
        not_injected = h.deployment("python-no-injection", "application")
        h.require(not_injected.has_no_injection())
