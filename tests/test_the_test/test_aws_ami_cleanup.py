from datetime import datetime, timedelta, UTC

from utils import features, scenarios
from utils.scripts.pulumi_clean_up import ami_cleanup_action, should_delete_ami

_NOW = datetime(2026, 10, 14, tzinfo=UTC)
_RETENTION_DAYS = 100
_LAST_LAUNCHED_DAYS = 111


def _action(
    tags: dict[str, str] | None,
    *,
    age_days: int,
    launched_days_ago: int | None,
    launch_lookup_ok: bool = True,
    retention_days: int = _RETENTION_DAYS,
    last_launched_days: int = _LAST_LAUNCHED_DAYS,
) -> str:
    last_launched = None if launched_days_ago is None else _NOW - timedelta(days=launched_days_ago)
    return ami_cleanup_action(
        tags,
        _NOW - timedelta(days=age_days),
        last_launched,
        _NOW,
        retention_days,
        last_launched_days,
        launch_lookup_ok=launch_lookup_ok,
    )


def _delete(
    tags: dict[str, str] | None,
    *,
    age_days: int,
    launched_days_ago: int | None,
    launch_lookup_ok: bool = True,
) -> bool:
    last_launched = None if launched_days_ago is None else _NOW - timedelta(days=launched_days_ago)
    return should_delete_ami(
        tags,
        _NOW - timedelta(days=age_days),
        last_launched,
        _NOW,
        _RETENTION_DAYS,
        _LAST_LAUNCHED_DAYS,
        launch_lookup_ok=launch_lookup_ok,
    )


@features.not_reported
@scenarios.test_the_test
class Test_AwsAmiCleanup:
    def test_recently_used_or_young_active_ami_is_retained(self) -> None:
        assert (
            _action({"ami-state": "active"}, age_days=10, launched_days_ago=1, retention_days=20, last_launched_days=5)
            == "keep"
        )
        assert (
            _action(
                {"ami-state": "active"}, age_days=1, launched_days_ago=None, retention_days=20, last_launched_days=5
            )
            == "keep"
        )
        assert (
            _action(
                {"ami-state": "active"},
                age_days=30,
                launched_days_ago=None,
                launch_lookup_ok=False,
                retention_days=20,
                last_launched_days=5,
            )
            == "keep"
        )

    def test_unused_active_ami_waits_one_cleanup_before_deletion(self) -> None:
        assert (
            _action({"ami-state": "active"}, age_days=3, launched_days_ago=6, retention_days=20, last_launched_days=5)
            == "mark"
        )
        assert (
            _action({"ami-state": "active"}, age_days=21, launched_days_ago=1, retention_days=20, last_launched_days=5)
            == "mark"
        )
        ready = {"ami-state": "active", "ami-retire-at": "2026-10-14T00:00:00Z"}
        waiting = {"ami-state": "active", "ami-retire-at": "2026-10-15T00:00:00Z"}
        assert _action(ready, age_days=21, launched_days_ago=6, retention_days=20, last_launched_days=5) == "delete"
        assert _action(waiting, age_days=21, launched_days_ago=6, retention_days=20, last_launched_days=5) == "keep"
        assert _action(ready, age_days=10, launched_days_ago=1, retention_days=20, last_launched_days=5) == "clear"

    def test_rejected_ami_is_deleted(self) -> None:
        assert _delete({"ami-state": "rejected"}, age_days=1, launched_days_ago=1) is True

    def test_recent_or_used_candidate_is_retained(self) -> None:
        assert (
            _action(
                {"ami-state": "candidate"}, age_days=1, launched_days_ago=None, retention_days=20, last_launched_days=5
            )
            == "keep"
        )
        assert (
            _action(
                {"ami-state": "candidate"}, age_days=10, launched_days_ago=1, retention_days=20, last_launched_days=5
            )
            == "keep"
        )

    def test_unused_candidate_waits_one_cleanup_before_deletion(self) -> None:
        assert (
            _action(
                {"ami-state": "candidate"}, age_days=3, launched_days_ago=6, retention_days=20, last_launched_days=5
            )
            == "mark"
        )
        ready = {"ami-state": "candidate", "ami-retire-at": "2026-10-13T00:00:00Z"}
        assert _action(ready, age_days=3, launched_days_ago=6, retention_days=20, last_launched_days=5) == "delete"

    def test_candidate_is_kept_when_recent_use_cannot_be_observed(self) -> None:
        assert (
            _action(
                {"ami-state": "candidate"},
                age_days=30,
                launched_days_ago=None,
                launch_lookup_ok=False,
                retention_days=20,
                last_launched_days=5,
            )
            == "keep"
        )

    def test_untagged_ami_follows_the_existing_cleanup_policy(self) -> None:
        assert _delete(None, age_days=1, launched_days_ago=1) is False
        assert _delete({}, age_days=200, launched_days_ago=1) is True
        assert _delete({"CI": "system-tests"}, age_days=1, launched_days_ago=None) is False
