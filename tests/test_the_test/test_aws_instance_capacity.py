from utils import features, scenarios
from utils.virtual_machine.aws_provider import (
    _MAX_EC2_INSTANCES,
    _counts_by_instance_type,
    _instance_count_summary,
)


@features.not_reported
@scenarios.test_the_test
class Test_AwsInstanceCapacity:
    def test_counts_instances_by_type(self) -> None:
        reservations = [
            {"Instances": [{"InstanceType": "t4g.medium"}, {"InstanceType": "t4g.medium"}]},
            {"Instances": [{"InstanceType": "t3.medium"}, {}]},
        ]

        counts = _counts_by_instance_type(reservations)

        assert counts == {"t4g.medium": 2, "t3.medium": 1, "unknown": 1}
        assert sum(counts.values()) == 4

    def test_empty_reservations_have_no_instances(self) -> None:
        assert _counts_by_instance_type([]) == {}
        assert _instance_count_summary({}) == "total=0"

    def test_summary_names_each_type(self) -> None:
        counts = {"t4g.medium": 400, "t3.medium": 327}

        assert _instance_count_summary(counts) == "total=727 (t3.medium=327, t4g.medium=400)"

    def test_cap_is_700_instances(self) -> None:
        assert _MAX_EC2_INSTANCES == 700
