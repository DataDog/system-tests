from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock

from utils import features, pytest, scenarios
from utils.virtual_machine.aws_provider import AWSPulumiProvider, _select_cached_ami


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
        assert _select_cached_ami([rejected_ami, candidate_ami]) is None
        assert _select_cached_ami([candidate_ami]) is None
        assert _select_cached_ami([rejected_ami]) is None

    def _configure(self, candidate: _CachedAmi, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        provider = AWSPulumiProvider()
        monkeypatch.setattr(provider, "_get_cached_amis", lambda _vm: [candidate])
        vm = MagicMock()
        vm.name = "Ubuntu_24"
        vm.datadog_config.skip_cache = False
        vm.datadog_config.update_cache = False
        vm.aws_config.ami_id = "ami-base"
        provider._configure_cached_amis(vm)  # noqa: SLF001
        return vm

    def test_recent_candidate_does_not_start_another_build(self, monkeypatch: pytest.MonkeyPatch) -> None:
        created = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        vm = self._configure(
            _CachedAmi(id="ami-candidate", creation_date=created, tags={"ami-state": "candidate"}), monkeypatch
        )

        assert vm.datadog_config.update_cache is False
        assert vm.datadog_config.skip_cache is True
        assert vm.aws_config.ami_id == "ami-base"

    def test_old_candidate_starts_a_new_build(self, monkeypatch: pytest.MonkeyPatch) -> None:
        vm = self._configure(
            _CachedAmi(id="ami-candidate", creation_date="2026-01-03T00:00:00Z", tags={"ami-state": "candidate"}),
            monkeypatch,
        )

        assert vm.datadog_config.update_cache is True
        assert vm.datadog_config.skip_cache is False
        assert vm.aws_config.ami_id == "ami-base"

    def test_pending_ami_is_returned_so_another_job_does_not_create_one(self) -> None:
        now = datetime(2026, 10, 14, 12, tzinfo=UTC)
        pending_ami = _CachedAmi(id="ami-pending", creation_date="2026-10-14T11:00:00Z", state="pending")
        pending_candidate = _CachedAmi(
            id="ami-pending-candidate",
            creation_date="2026-10-14T10:00:00Z",
            state="pending",
            tags={"ami-state": "candidate"},
        )

        assert _select_cached_ami([pending_ami], now=now) is pending_ami
        assert _select_cached_ami([pending_candidate], now=now) is pending_candidate

    def test_stale_pending_candidate_does_not_block_a_new_build(self) -> None:
        now = datetime(2026, 10, 14, 12, tzinfo=UTC)
        stale = _CachedAmi(
            id="ami-stale",
            creation_date="2026-10-13T00:00:00Z",
            state="pending",
            tags={"ami-state": "candidate"},
        )

        assert _select_cached_ami([stale], now=now) is None

    def test_fresh_candidate_blocks_ahead_of_an_older_one(self) -> None:
        now = datetime(2026, 10, 14, 12, tzinfo=UTC)
        stale = _CachedAmi(
            id="ami-old",
            creation_date="2026-10-13T00:00:00Z",
            tags={"ami-state": "candidate"},
        )
        fresh = _CachedAmi(
            id="ami-fresh",
            creation_date="2026-10-14T11:00:00Z",
            tags={"ami-state": "candidate"},
        )

        assert _select_cached_ami([stale, fresh], now=now) is fresh
