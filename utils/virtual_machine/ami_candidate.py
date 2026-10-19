from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, UTC
from typing import Protocol

_CANDIDATE_BUILD_WINDOW = timedelta(hours=6)
_REJECTED_AMI_STATE = "rejected"


class _SelectableAmi(Protocol):
    creation_date: str
    state: object
    tags: Mapping[str, str] | None


def candidate_result_state(exitstatus: int, *, provision_failed: bool, test_outcomes: Sequence[str]) -> str | None:
    """Promote only after a real pass. Reject only after a real test failure."""
    if provision_failed or not any(outcome in {"pass", "fail"} for outcome in test_outcomes):
        return None
    if "fail" in test_outcomes:
        return "rejected"
    if exitstatus == 0:
        return "active"
    return None


def should_boot_created_candidate(*, update_cache: bool, skip_cache: bool) -> bool:
    """Boot the AMI created by this job, without replacing an existing cache."""
    return update_cache and not skip_cache


def _ami_state(ami: _SelectableAmi) -> str | None:
    return (ami.tags or {}).get("ami-state")


def _created_at(ami: _SelectableAmi) -> datetime:
    created = datetime.fromisoformat(str(ami.creation_date))
    if created.tzinfo is None:
        return created.replace(tzinfo=UTC)
    return created


def _still_building(ami: _SelectableAmi, now: datetime) -> bool:
    in_progress = str(ami.state) != "available" or _ami_state(ami) == "candidate"
    return in_progress and now - _created_at(ami) < _CANDIDATE_BUILD_WINDOW


def select_usable_ami[AmiT: _SelectableAmi](amis: Sequence[AmiT], *, now: datetime | None = None) -> AmiT | None:
    """Prefer the newest active AMI, then an untagged AMI. Never boot a candidate or rejected AMI."""
    current = now or datetime.now(UTC)
    usable = [ami for ami in amis if _ami_state(ami) != _REJECTED_AMI_STATE]
    available = [ami for ami in usable if str(ami.state) == "available" and _ami_state(ami) != "candidate"]
    active_amis = [ami for ami in available if _ami_state(ami) == "active"]
    if active_amis:
        return max(active_amis, key=lambda ami: ami.creation_date)
    for ami in available:
        if _ami_state(ami) is None:
            return ami
    building = [ami for ami in usable if _still_building(ami, current)]
    if not building:
        return None
    return max(building, key=lambda ami: ami.creation_date)


def cache_plan(ami: _SelectableAmi | None, *, now: datetime | None = None) -> str:
    """Return create, wait, or use. A candidate blocks a second build for six hours."""
    if ami is None:
        return "create"
    if str(ami.state) == "available" and _ami_state(ami) != "candidate":
        return "use"
    if _still_building(ami, now or datetime.now(UTC)):
        return "wait"
    return "create"


def candidate_state_tags(tags: Mapping[str, str], cache_key: str, new_state: str) -> list[dict[str, str]] | None:
    """Return a tag update for the candidate created by this job."""
    owned_candidate = (
        tags.get("CI") == "system-tests"
        and tags.get("ami-state") == "candidate"
        and tags.get("ami-cache-key") == cache_key
    )
    if not owned_candidate:
        return None
    return [{"Key": "ami-state", "Value": new_state}]


def candidate_promotion_tags(tags: Mapping[str, str], cache_key: str) -> list[dict[str, str]] | None:
    """Return the active tag for the candidate created by this job."""
    return candidate_state_tags(tags, cache_key, "active")


class _Ec2Images(Protocol):
    def describe_images(self, **kwargs: object) -> dict[str, list[dict[str, list[dict[str, str]]]]]: ...

    def create_tags(self, **kwargs: object) -> None: ...


def set_created_candidate_state(ec2: _Ec2Images, ami_id: str, cache_key: str, new_state: str) -> bool:
    """Update one candidate tag. This never deregisters or deletes an AMI."""
    images = ec2.describe_images(ImageIds=[ami_id], Owners=["self"]).get("Images", [])
    if len(images) != 1:
        return False
    tags = {item["Key"]: item["Value"] for item in images[0].get("Tags", [])}
    update = candidate_state_tags(tags, cache_key, new_state)
    if update is None:
        return False
    ec2.create_tags(Resources=[ami_id], Tags=update)
    return True


def promote_created_candidate(ec2: _Ec2Images, ami_id: str, cache_key: str) -> bool:
    """Mark one candidate active."""
    return set_created_candidate_state(ec2, ami_id, cache_key, "active")


def reject_created_candidate(ec2: _Ec2Images, ami_id: str, cache_key: str) -> bool:
    """Mark one candidate rejected so later jobs create a replacement."""
    return set_created_candidate_state(ec2, ami_id, cache_key, "rejected")
