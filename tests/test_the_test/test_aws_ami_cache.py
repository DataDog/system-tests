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

    def test_newest_active_ami_is_selected(self) -> None:
        older_active_ami = _CachedAmi(
            id="ami-active-old",
            creation_date="2026-01-01T00:00:00Z",
            tags={"ami-state": "active"},
        )
        newer_active_ami = _CachedAmi(
            id="ami-active-new",
            creation_date="2026-02-01T00:00:00Z",
            tags={"ami-state": "active"},
        )
        legacy_ami = _CachedAmi(id="ami-legacy", creation_date="2026-03-01T00:00:00Z")

        assert _select_cached_ami([older_active_ami, legacy_ami, newer_active_ami]) is newer_active_ami

    def test_candidate_and_rejected_amis_are_not_selected(self) -> None:
        legacy_ami = _CachedAmi(id="ami-legacy", creation_date="2026-01-01T00:00:00Z")
        candidate_ami = _CachedAmi(
            id="ami-candidate",
            creation_date="2026-01-03T00:00:00Z",
            tags={"ami-state": "candidate"},
        )
        rejected_ami = _CachedAmi(
            id="ami-rejected",
            creation_date="2026-01-04T00:00:00Z",
            tags={"ami-state": "rejected"},
        )

        assert _select_cached_ami([candidate_ami, rejected_ami, legacy_ami]) is legacy_ami
        assert _select_cached_ami([rejected_ami, candidate_ami]) is candidate_ami
        assert _select_cached_ami([rejected_ami]) is None

    def test_pending_ami_is_returned_so_another_job_does_not_create_one(self) -> None:
        pending_ami = _CachedAmi(id="ami-pending", creation_date="2026-01-01T00:00:00Z", state="pending")

        assert _select_cached_ami([pending_ami]) is pending_ami
