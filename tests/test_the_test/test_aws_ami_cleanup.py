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
) -> str:
    last_launched = None if launched_days_ago is None else _NOW - timedelta(days=launched_days_ago)
    return ami_cleanup_action(
        tags,
        _NOW - timedelta(days=age_days),
        last_launched,
        _NOW,
        _RETENTION_DAYS,
        _LAST_LAUNCHED_DAYS,
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
        assert _delete({"ami-state": "active"}, age_days=9, launched_days_ago=1) is False
        assert _delete({"ami-state": "active"}, age_days=1, launched_days_ago=None) is False
        assert _delete({"ami-state": "active"}, age_days=9, launched_days_ago=None, launch_lookup_ok=False) is False

    def test_unused_active_ami_waits_one_cleanup_before_deletion(self) -> None:
        assert _action({"ami-state": "active"}, age_days=9, launched_days_ago=9) == "mark"
        ready = {"ami-state": "active", "ami-retire-at": "2026-10-14T00:00:00Z"}
        waiting = {"ami-state": "active", "ami-retire-at": "2026-10-15T00:00:00Z"}
        assert _action(ready, age_days=9, launched_days_ago=9) == "delete"
        assert _action(waiting, age_days=9, launched_days_ago=9) == "keep"
        assert _action(ready, age_days=9, launched_days_ago=1) == "clear"

    def test_rejected_ami_is_deleted(self) -> None:
        assert _delete({"ami-state": "rejected"}, age_days=1, launched_days_ago=1) is True

    def test_recent_or_used_candidate_is_retained(self) -> None:
        assert _delete({"ami-state": "candidate"}, age_days=1, launched_days_ago=None) is False
        assert _delete({"ami-state": "candidate"}, age_days=8, launched_days_ago=1) is False

    def test_unused_candidate_waits_one_cleanup_before_deletion(self) -> None:
        assert _action({"ami-state": "candidate"}, age_days=9, launched_days_ago=None) == "mark"
        ready = {"ami-state": "candidate", "ami-retire-at": "2026-10-13T00:00:00Z"}
        assert _action(ready, age_days=9, launched_days_ago=9) == "delete"

    def test_candidate_is_kept_when_recent_use_cannot_be_observed(self) -> None:
        assert _delete({"ami-state": "candidate"}, age_days=9, launched_days_ago=None, launch_lookup_ok=False) is False
        assert _delete({"ami-state": "candidate"}, age_days=8, launched_days_ago=8) is False

    def test_untagged_ami_follows_the_existing_cleanup_policy(self) -> None:
        assert _delete(None, age_days=1, launched_days_ago=1) is False
        assert _delete({}, age_days=200, launched_days_ago=1) is True
        assert _delete({"CI": "system-tests"}, age_days=1, launched_days_ago=None) is False
