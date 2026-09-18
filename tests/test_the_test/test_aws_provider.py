# ruff: noqa: SLF001

from collections.abc import Callable
from typing import Any

import pytest

from utils import features, scenarios
from utils.virtual_machine import aws_provider
from utils.virtual_machine.virtual_machines import AWSInfraConfig


class _CommandError(Exception):
    pass


class _Stack:
    def __init__(self, outcomes: list[Exception | None]) -> None:
        self.outcomes = outcomes
        self.up_calls = 0

    def up(self, *, on_output: Callable[[str], Any]) -> None:
        del on_output
        outcome = self.outcomes[self.up_calls]
        self.up_calls += 1
        if outcome is not None:
            raise outcome


@features.not_reported
@scenarios.test_the_test
class Test_AWSProvider:
    def test_infra_config_normalizes_comma_separated_ids(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ONBOARDING_AWS_INFRA_SUBNET_ID", " subnet-a,subnet-b, ,subnet-c ")
        monkeypatch.setenv("ONBOARDING_AWS_INFRA_SECURITY_GROUPS_ID", " sg-a, sg-b ")

        config = AWSInfraConfig()

        assert config.subnet_id == ["subnet-a", "subnet-b", "subnet-c"]
        assert config.vpc_security_group_ids == ["sg-a", "sg-b"]

    def test_capacity_failure_rotates_through_subnets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(aws_provider.pulumi.automation.errors, "CommandError", _CommandError)
        provider = aws_provider.AWSPulumiProvider()
        provider._subnet_ids = ["subnet-a", "subnet-b", "subnet-c"]
        provider.stack = _Stack(
            [
                _CommandError("InsufficientInstanceCapacity"),
                _CommandError("InsufficientInstanceCapacity"),
                None,
            ]
        )
        destroyed_subnets: list[str] = []
        monkeypatch.setattr(
            provider,
            "stack_destroy",
            lambda: destroyed_subnets.append(provider._subnet_ids[provider._subnet_index]),
        )

        provider._stack_up_with_transient_retry()

        assert provider.stack.up_calls == 3
        assert provider._subnet_index == 2
        assert destroyed_subnets == ["subnet-b", "subnet-c"]

    def test_capacity_failure_is_raised_after_all_subnets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(aws_provider.pulumi.automation.errors, "CommandError", _CommandError)
        provider = aws_provider.AWSPulumiProvider()
        provider._subnet_ids = ["subnet-a", "subnet-b"]
        provider.stack = _Stack(
            [
                _CommandError("InsufficientInstanceCapacity"),
                _CommandError("InsufficientInstanceCapacity"),
            ]
        )
        monkeypatch.setattr(provider, "stack_destroy", lambda: None)

        with pytest.raises(_CommandError, match="InsufficientInstanceCapacity"):
            provider._stack_up_with_transient_retry()

        assert provider.stack.up_calls == 2
        assert provider._subnet_index == 1

    def test_idempotency_failure_retries_without_rotating_subnet(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(aws_provider.pulumi.automation.errors, "CommandError", _CommandError)
        provider = aws_provider.AWSPulumiProvider()
        provider._subnet_ids = ["subnet-a", "subnet-b"]
        provider.stack = _Stack([_CommandError("IdempotentParameterMismatch"), None])
        destroy_calls = 0

        def record_destroy() -> None:
            nonlocal destroy_calls
            destroy_calls += 1

        monkeypatch.setattr(provider, "stack_destroy", record_destroy)

        provider._stack_up_with_transient_retry()

        assert provider.stack.up_calls == 2
        assert provider._subnet_index == 0
        assert destroy_calls == 1
