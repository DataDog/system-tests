from utils import features, scenarios
from utils.virtual_machine.aws_provider import (
    _MAX_EC2_INSTANCES,
    _count_instances,
    _ec2_instance_filters,
)


@features.not_reported
@scenarios.test_the_test
class Test_AwsInstanceCapacity:
    def test_filters_select_the_instance_type_being_launched(self) -> None:
        filters = {item["Name"]: item["Values"] for item in _ec2_instance_filters("t4g.medium")}

        assert filters["instance-type"] == ["t4g.medium"]
        assert filters["instance-state-name"] == ["pending", "running"]
        assert filters["tag:CI"] == ["system-tests"]

    def test_counts_instances_in_the_reservations(self) -> None:
        reservations = [
            {"Instances": [{"InstanceType": "t4g.medium"}, {"InstanceType": "t4g.medium"}]},
            {"Instances": []},
        ]

        assert _count_instances(reservations) == 2
        assert _count_instances([]) == 0

    def test_cap_is_700_instances_of_one_type(self) -> None:
        assert _MAX_EC2_INSTANCES == 700
