from unittest.mock import MagicMock

from utils import features, pytest, scenarios
from utils.virtual_machine.ami_candidate import (
    candidate_promotion_tags,
    candidate_result_state,
    promote_created_candidate,
    reject_created_candidate,
    should_boot_created_candidate,
)
from utils.virtual_machine.aws_provider import AWSPulumiProvider

_CACHE_KEY = "Ubuntu_24_java_test-app_83cba9f5"


class _FakeEc2:
    def __init__(self, tags: dict[str, str] | None) -> None:
        self.tags = tags
        self.tagged: dict[str, object] | None = None

    def describe_images(self, **_kwargs: object) -> dict[str, list[dict[str, list[dict[str, str]]]]]:
        if self.tags is None:
            return {"Images": []}
        return {"Images": [{"Tags": [{"Key": key, "Value": value} for key, value in self.tags.items()]}]}

    def create_tags(self, **kwargs: object) -> None:
        self.tagged = kwargs


@scenarios.test_the_test
@features.not_reported
class Test_AwsAmiCandidateBoot:
    def test_candidate_state_follows_only_executed_tests(self) -> None:
        assert candidate_result_state(0, provision_failed=False, test_outcomes=["passed"]) == "active"
        assert candidate_result_state(0, provision_failed=False, test_outcomes=["xpassed"]) == "active"
        assert candidate_result_state(0, provision_failed=False, test_outcomes=["xfailed"]) == "active"
        assert candidate_result_state(1, provision_failed=False, test_outcomes=["passed", "failed"]) == "rejected"
        assert candidate_result_state(1, provision_failed=False, test_outcomes=["error"]) == "rejected"
        assert candidate_result_state(1, provision_failed=True, test_outcomes=["failed"]) is None
        assert candidate_result_state(0, provision_failed=False, test_outcomes=["skipped"]) is None
        assert candidate_result_state(0, provision_failed=False, test_outcomes=[]) is None
        assert candidate_result_state(3, provision_failed=False, test_outcomes=["passed"]) is None

    def test_cache_creation_boots_the_candidate(self) -> None:
        assert should_boot_created_candidate(update_cache=True, skip_cache=False) is True
        assert should_boot_created_candidate(update_cache=False, skip_cache=False) is False
        assert should_boot_created_candidate(update_cache=True, skip_cache=True) is False

    def test_only_the_candidate_created_for_this_cache_can_become_active(self) -> None:
        candidate = {"CI": "system-tests", "ami-state": "candidate", "ami-cache-key": _CACHE_KEY}
        assert candidate_promotion_tags(candidate, _CACHE_KEY) == [{"Key": "ami-state", "Value": "active"}]
        assert candidate_promotion_tags({"CI": "system-tests", "ami-state": "active"}, _CACHE_KEY) is None
        assert candidate_promotion_tags({"ami-state": "candidate", "ami-cache-key": _CACHE_KEY}, _CACHE_KEY) is None
        assert candidate_promotion_tags(candidate, "another-cache") is None

    def test_promotion_does_not_touch_an_existing_ami(self) -> None:
        active = _FakeEc2({"CI": "system-tests", "ami-state": "active", "ami-cache-key": _CACHE_KEY})
        missing = _FakeEc2(None)

        assert promote_created_candidate(active, "ami-active", _CACHE_KEY) is False
        assert promote_created_candidate(missing, "ami-missing", _CACHE_KEY) is False
        assert active.tagged is None
        assert missing.tagged is None

    def test_promotion_only_replaces_the_candidate_state(self) -> None:
        ec2 = _FakeEc2({"CI": "system-tests", "ami-state": "candidate", "ami-cache-key": _CACHE_KEY})

        assert promote_created_candidate(ec2, "ami-new", _CACHE_KEY) is True
        assert ec2.tagged == {
            "Resources": ["ami-new"],
            "Tags": [{"Key": "ami-state", "Value": "active"}],
        }

    def test_rejection_only_replaces_the_candidate_state(self) -> None:
        ec2 = _FakeEc2({"CI": "system-tests", "ami-state": "candidate", "ami-cache-key": _CACHE_KEY})
        active = _FakeEc2({"CI": "system-tests", "ami-state": "active", "ami-cache-key": _CACHE_KEY})

        assert reject_created_candidate(ec2, "ami-new", _CACHE_KEY) is True
        assert reject_created_candidate(active, "ami-active", _CACHE_KEY) is False
        assert ec2.tagged == {
            "Resources": ["ami-new"],
            "Tags": [{"Key": "ami-state", "Value": "rejected"}],
        }
        assert active.tagged is None

    def test_failed_job_rejects_only_the_booted_candidate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = AWSPulumiProvider()
        provider.booted_candidate_ami_id = "ami-new"
        provider.vm = MagicMock()
        provider.vm.get_cache_name.return_value = _CACHE_KEY
        monkeypatch.setattr("utils.virtual_machine.aws_candidate_boot.boto3.client", lambda *_args, **_kwargs: object())
        rejected: list[tuple[object, ...]] = []

        def _record_state(*args: object) -> bool:
            rejected.append(args)
            return True

        monkeypatch.setattr(
            "utils.virtual_machine.aws_candidate_boot.set_created_candidate_state",
            _record_state,
        )

        provider.promote_booted_candidate("rejected")

        assert len(rejected) == 1
        assert rejected[0][1:] == ("ami-new", _CACHE_KEY, "rejected")

    def test_infrastructure_failure_leaves_the_candidate_unchanged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = AWSPulumiProvider()
        provider.booted_candidate_ami_id = "ami-new"
        provider.vm = MagicMock()
        marker = MagicMock()
        monkeypatch.setattr("utils.virtual_machine.aws_candidate_boot.set_created_candidate_state", marker)

        provider.promote_booted_candidate(None)

        marker.assert_not_called()

    def test_disabled_job_keeps_the_builder_instance(self) -> None:
        provider = AWSPulumiProvider()
        provider.boot_created_candidate = False
        provider._launch_instance = MagicMock()  # noqa: SLF001
        vm = MagicMock()
        vm.datadog_config.update_cache = True
        vm.datadog_config.skip_cache = False
        server, connection, created_cache = MagicMock(), MagicMock(), MagicMock()

        assert provider.use_created_cache(vm, server, connection, created_cache) == (server, connection, created_cache)
        provider._launch_instance.assert_not_called()  # noqa: SLF001

    def test_enabled_job_boots_the_candidate_created_in_that_job(self) -> None:
        provider = AWSPulumiProvider()
        provider.boot_created_candidate = True
        provider.instance_user_data = "windows-ssh"
        candidate, connection = MagicMock(), MagicMock()
        provider._launch_instance = MagicMock(return_value=(candidate, connection))  # noqa: SLF001
        created_cache = MagicMock()
        created_cache.id.apply = lambda callback: callback("ami-new")
        vm = MagicMock()
        vm.name = "Ubuntu_24"
        vm.datadog_config.update_cache = True
        vm.datadog_config.skip_cache = False

        assert provider.use_created_cache(vm, MagicMock(), MagicMock(), created_cache) == (
            candidate,
            connection,
            candidate,
        )
        assert provider._launch_instance.call_args.args[1] is created_cache.id  # noqa: SLF001
        assert provider._launch_instance.call_args.args[3] == "windows-ssh"  # noqa: SLF001
        assert provider.booted_candidate_ami_id == "ami-new"
