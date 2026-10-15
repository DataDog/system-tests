from datetime import datetime, timedelta, UTC

from utils import features, scenarios
from utils.scripts.pulumi_clean_up import should_delete_ami

_NOW = datetime(2026, 10, 14, tzinfo=UTC)
_RETENTION_DAYS = 100
_LAST_LAUNCHED_DAYS = 111


def _delete(
    tags: dict[str, str] | None,
    *,
    age_days: int,
    launched_days_ago: int | None,
) -> bool:
    last_launched = None if launched_days_ago is None else _NOW - timedelta(days=launched_days_ago)
    return should_delete_ami(
        tags,
        _NOW - timedelta(days=age_days),
        last_launched,
        _NOW,
        _RETENTION_DAYS,
        _LAST_LAUNCHED_DAYS,
    )


@features.not_reported
@scenarios.test_the_test
class Test_AwsAmiCleanup:
    def test_active_ami_is_retained(self) -> None:
        assert _delete({"ami-state": "active"}, age_days=200, launched_days_ago=200) is False

    def test_recent_or_used_candidate_is_retained(self) -> None:
        assert _delete({"ami-state": "candidate"}, age_days=1, launched_days_ago=None) is False
        assert _delete({"ami-state": "candidate"}, age_days=8, launched_days_ago=1) is False

    def test_unused_candidate_is_deleted(self) -> None:
        assert _delete({"ami-state": "candidate"}, age_days=8, launched_days_ago=None) is True
        assert _delete({"ami-state": "candidate"}, age_days=8, launched_days_ago=8) is True

    def test_untagged_ami_follows_the_existing_cleanup_policy(self) -> None:
        assert _delete(None, age_days=1, launched_days_ago=1) is False
        assert _delete({}, age_days=200, launched_days_ago=1) is True
        assert _delete({"CI": "system-tests"}, age_days=1, launched_days_ago=None) is False
