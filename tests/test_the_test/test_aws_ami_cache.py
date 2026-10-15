from dataclasses import dataclass, field

from utils import features, scenarios
from utils.virtual_machine.aws_provider import _select_cached_ami


@dataclass(frozen=True)
class _CachedAmi:
    id: str
    creation_date: str
    state: str = "available"
    tags: dict[str, str] = field(default_factory=dict)


@features.not_reported
@scenarios.test_the_test
class Test_AwsAmiCache:
    def test_active_ami_has_priority_over_legacy_ami(self) -> None:
        legacy_ami = _CachedAmi(id="ami-legacy", creation_date="2026-01-02T00:00:00Z")
        active_ami = _CachedAmi(
            id="ami-active",
            creation_date="2026-01-01T00:00:00Z",
            tags={"ami-state": "active"},
        )

        assert _select_cached_ami([legacy_ami, active_ami]) is active_ami

    def test_current_first_match_behavior_is_preserved_without_active_ami(self) -> None:
        first_ami = _CachedAmi(id="ami-first", creation_date="2026-01-01T00:00:00Z")
        second_ami = _CachedAmi(id="ami-second", creation_date="2026-01-02T00:00:00Z")

        assert _select_cached_ami([first_ami, second_ami]) is first_ami

    def test_unavailable_active_ami_does_not_override_current_behavior(self) -> None:
        legacy_ami = _CachedAmi(id="ami-legacy", creation_date="2026-01-01T00:00:00Z")
        pending_active_ami = _CachedAmi(
            id="ami-active",
            creation_date="2026-01-02T00:00:00Z",
            state="pending",
            tags={"ami-state": "active"},
        )

        assert _select_cached_ami([legacy_ami, pending_active_ami]) is legacy_ami

    def test_no_cached_ami_returns_none(self) -> None:
        assert _select_cached_ami([]) is None
