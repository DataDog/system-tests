from unittest.mock import MagicMock

from utils import features, pytest, scenarios
from utils.virtual_machine import aws_provider


@scenarios.test_the_test
@features.not_reported
class Test_AWSAmiCacheCreation:
    def test_created_ami_is_a_candidate_with_its_cache_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cache_key = "Ubuntu_24_java_test-app_83cba9f5"
        vm = MagicMock()
        vm.get_cache_name.return_value = cache_key
        server = MagicMock()
        server.id = "i-source"
        last_task = MagicMock()
        created_ami = MagicMock()
        create_ami = MagicMock(return_value=created_ami)

        monkeypatch.setattr(aws_provider.aws.ec2, "AmiFromInstance", create_ami)
        monkeypatch.setattr(aws_provider.pulumi, "ResourceOptions", MagicMock())
        monkeypatch.setattr(aws_provider, "vm_logger", MagicMock())

        result = aws_provider.AWSCommander().create_cache(vm, server, last_task)

        assert result is created_ami
        assert create_ami.call_args.kwargs["tags"] == {
            "CI": "system-tests",
            "ami-cache-key": cache_key,
            "ami-state": "candidate",
        }
