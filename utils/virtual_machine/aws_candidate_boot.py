import os
import uuid
import random

import boto3
import pulumi
import pulumi_aws as aws
import pulumi_command as command
from pulumi import Output

from utils import context
from utils._logger import logger
from utils.virtual_machine.ami_candidate import set_created_candidate_state
from collections.abc import Mapping
from typing import Protocol, cast

from utils.virtual_machine.virtual_machines import _VirtualMachine
from utils.virtual_machine.vm_logger import vm_logger


class _CreatedAmi(Protocol):
    id: pulumi.Output[str]


class _PulumiSsh(Protocol):
    aws_key_resource: pulumi.ResourceOptions | None
    keypair_name: str | pulumi.Output[str] | None
    private_key_pem: str | pulumi.Output[str] | None


class CandidateBoot:
    """Boot and promote only the candidate created by the current job."""

    booted_candidate_ami_id: str | None
    boot_created_candidate: bool
    instance_user_data: str | None
    pulumi_ssh: _PulumiSsh
    vm: _VirtualMachine

    def _get_ec2_tags(self, vm: _VirtualMachine) -> Mapping[str, str]:
        raise NotImplementedError

    def _launch_instance(
        self,
        vm: _VirtualMachine,
        ami_id: str | pulumi.Output[str],
        depends_on: _CreatedAmi | None,
        user_data: str | None,
        *,
        publish_ip: bool,
        name_suffix: str,
        export_suffix: str = "",
    ) -> tuple[aws.ec2.Instance, command.remote.ConnectionArgs]:
        """Launch one EC2 instance. The resource name stays unique per CI job."""
        logger.info(
            f"Starting VM: {vm.name} with iam_instance_profile: {vm.aws_config.aws_infra_config.iam_instance_profile}"
        )
        opts = self.pulumi_ssh.aws_key_resource
        if depends_on is not None:
            opts = pulumi.ResourceOptions.merge(
                opts, pulumi.ResourceOptions(depends_on=[cast("pulumi.Resource", depends_on)])
            )
        ec2_server = aws.ec2.Instance(
            f"{vm.name}{name_suffix}-{os.getenv('CI_JOB_ID', uuid.uuid4())}",
            instance_type=vm.aws_config.ami_instance_type,
            vpc_security_group_ids=vm.aws_config.aws_infra_config.vpc_security_group_ids,
            subnet_id=random.choice(vm.aws_config.aws_infra_config.subnet_id),
            key_name=self.pulumi_ssh.keypair_name,
            ami=ami_id,
            tags=dict(self._get_ec2_tags(vm)),
            opts=opts,
            root_block_device={"volume_size": vm.aws_config.volume_size},
            iam_instance_profile=vm.aws_config.aws_infra_config.iam_instance_profile,
            user_data=user_data,
        )
        if publish_ip:
            ip_output = ec2_server.private_ip
            if depends_on is not None:
                ip_output = Output.all(ec2_server.private_ip, depends_on.id).apply(lambda args: args[0])
            ip_output.apply(lambda ip: vm.set_ip(ip))
            pulumi.export(f"privateIp_{vm.name}{export_suffix}", ec2_server.private_ip)
            Output.all(ec2_server.private_ip, vm.name, ec2_server.id).apply(
                lambda args: vm_logger(context.scenario.host_log_folder, "vms_desc").info(
                    f"{args[0]}:{args[1]}:{args[2]}"
                )
            )
        vm.ssh_config.username = vm.aws_config.user
        connection = command.remote.ConnectionArgs(
            host=ec2_server.private_ip,
            user=vm.aws_config.user,
            private_key=self.pulumi_ssh.private_key_pem,
            # dial_error_limit=30 retries, 10 seconds per retry=5 minutes.
            # WARNING:: If you change that, please change the key 'error_ssh_connection' in aws_infra_exceptions.json
            dial_error_limit=30,
            per_dial_timeout=10,
        )
        return ec2_server, connection

    def use_created_cache(
        self, vm: _VirtualMachine, server: object, server_connection: object, created_cache: object
    ) -> tuple[object, object, object]:
        """Boot the candidate created by this job when the pipeline explicitly opts in."""
        if not self.boot_created_candidate:
            return server, server_connection, created_cache
        logger.stdout(f"Booting [{vm.name}] from the candidate AMI created in this job")
        created = cast("_CreatedAmi", created_cache)
        candidate, connection = self._launch_instance(
            vm,
            created.id,
            created,
            self.instance_user_data,
            publish_ip=True,
            name_suffix="-candidate",
            export_suffix="",
        )
        created.id.apply(lambda ami_id: setattr(self, "booted_candidate_ami_id", ami_id))
        return candidate, connection, candidate

    def promote_booted_candidate(self, new_state: str | None) -> None:
        """Apply active or rejected only after tests ran against this candidate."""
        if new_state not in {"active", "rejected"} or not self.booted_candidate_ami_id:
            return
        try:
            changed = set_created_candidate_state(
                boto3.client("ec2"),
                self.booted_candidate_ami_id,
                self.vm.get_cache_name(),
                new_state,
            )
        except Exception as error:
            logger.exception(error)
            return
        logger.stdout(f"Candidate [{self.booted_candidate_ami_id}] {new_state}={changed}")
