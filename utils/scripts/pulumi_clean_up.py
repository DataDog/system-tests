import os
import time
import argparse
import subprocess
import json
from typing import Any

import boto3
from botocore.exceptions import ClientError
from collections.abc import Callable, Coroutine
import pulumi
import pulumi_aws as aws
from pulumi import automation as auto
from datetime import datetime, timedelta, UTC
from pulumi import Config
import pulumi_command as command

# Define retention settings
DEFAULT_AMI_RETENTION_DAYS = 100
DEFAULT_AMI_LAST_LAUNCHED_DAYS = 111


def get_last_launched_time(ami_id: str) -> datetime:
    """Fetches the last launched time of an AMI using AWS CLI.
    https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ami-last-launched-time.html
    Considerations: When the AMI is used to launch an instance, there is a 24-hour delay before that usage is reported.
    """
    try:
        result = subprocess.run(
            [
                "aws",
                "ec2",
                "describe-image-attribute",
                "--image-id",
                ami_id,
                "--attribute",
                "lastLaunchedTime",
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        if data:
            last_launched_time = data.get("LastLaunchedTime").get("Value", None)

            if last_launched_time:
                return datetime.fromisoformat(last_launched_time.replace("Z", "+00:00"))
    except Exception as e:
        print(f"⚠️ Failed to fetch last launched time for AMI {ami_id}: {e}")

    # Return today's date if LastLaunchedTime is missing
    return datetime.now(UTC)


def deregister_ami(ami_id: str) -> None:
    """Deregisters an AMI using AWS CLI."""
    try:
        subprocess.run(["aws", "ec2", "deregister-image", "--image-id", ami_id], check=True)
        print(f"✅ Successfully deregistered AMI {ami_id}")
    except Exception as e:
        print(f"⚠️ Failed to deregister AMI {ami_id}: {e}")


def delete_snapshot(snapshot_id: str) -> None:
    """Deletes a snapshot using AWS CLI."""
    try:
        subprocess.run(["aws", "ec2", "delete-snapshot", "--snapshot-id", snapshot_id], check=True)
        print(f"✅ Successfully deleted snapshot {snapshot_id}")
    except Exception as e:
        print(f"⚠️ Failed to delete snapshot {snapshot_id}: {e}")


def delete_ami(ami: aws.ec2.Ami) -> None:
    # Deregister the AMI using AWS CLI
    deregister_ami(ami.id)

    for block in ami.block_device_mappings:
        if "ebs" in block and "snapshot_id" in block["ebs"]:
            snapshot_id = block["ebs"]["snapshot_id"]
            print(f"🗑️ Deleting snapshot: {snapshot_id}")
            delete_snapshot(snapshot_id)


def get_instance_launch_time(instance_id: str, region: str = "us-east-1") -> str | None:
    """Given an ec2 instance id, return the launch time of the instance
    This method uses aws client instead of pulumi, due to pulumi in the CI doesn't get the launch time (why?)
    """

    ec2 = boto3.client("ec2", region_name=region)

    try:
        response = ec2.describe_instances(InstanceIds=[instance_id])
        reservations = response.get("Reservations", [])

        if not reservations:
            print(f"Instance {instance_id} not found.")
            return None

        instance = reservations[0]["Instances"][0]
        launch_time = instance["LaunchTime"]  # This is a datetime object (UTC)
        return launch_time.isoformat()

    except ClientError as e:
        print(f"Error retrieving instance: {e}")
        return None


def count_system_tests_amis() -> int:
    """Counts the number of AMIs with a system-tests tag.

    Returns:
        int: Number of matching AMIs.

    """
    try:
        result = subprocess.run(
            [
                "aws",
                "ec2",
                "describe-images",
                "--owners",
                "self",
                "--filters",
                "Name=tag:CI,Values=system-tests",
                "--query",
                "Images | length(@)",
                "--output",
                "text",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return int(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print("❌ AWS CLI command failed:")
        print(e.stderr)
        return -1


def send_amis_count_to_datadog(num_amis: int) -> None:
    """Sends a custom Datadog gauge metric using curl via subprocess.

    Args:
        num_amis (int): The numeric value to send (e.g., number of AMIs).

    """
    metric_name = "custom.count_amis"
    default_tags = ["repository:system-tests", "source:pulumi", "metric:ami_count"]
    ddev_api_key = os.getenv("DDEV_API_KEY")
    if not ddev_api_key:
        print("Datadog API key not found to send event to ddev organization. Skipping event.")
        return
    payload = {
        "series": [
            {
                "metric": metric_name,
                "points": [[int(time.time()), num_amis]],
                "type": "gauge",
                "tags": default_tags,
                "host": "custom_script",
            }
        ]
    }

    curl_command = [
        "curl",
        "-X",
        "POST",
        "https://api.datadoghq.com/api/v1/series",
        "-H",
        "Content-Type: application/json",
        "-H",
        f"DD-API-KEY: {ddev_api_key}",
        "-d",
        json.dumps(payload),
    ]

    print(f"📤 Sending metric: {metric_name} = {num_amis} with tags {default_tags}")
    result = subprocess.run(curl_command, capture_output=True, text=True, check=False)

    if result.returncode == 0:
        print("✅ Metric sent successfully")
    else:
        print("❌ Failed to send metric")
        print("stderr:", result.stderr)
        print("stdout:", result.stdout)


async def clean_up_amis() -> None:
    """Clean up obsolote amis based on parameters ami_retention_days and last launched date"""
    config = Config()
    ami_retention_days = int(config.require("ami_retention_days"))
    ami_last_launched_days = int(config.require("ami_last_launched_days"))

    cutoff_creation_date = datetime.now(UTC) - timedelta(days=ami_retention_days)
    cutoff_last_launched_date = datetime.now(UTC) - timedelta(days=ami_last_launched_days)

    print(f"🧹 Removing AMIs older than {ami_retention_days} days and not launched in {ami_last_launched_days} days")

    # Fetch all AMIs owned by the current AWS account with the CI=system-tests tag
    ami_ids = (await aws.ec2.get_ami_ids(owners=["self"], filters=[{"name": "tag:CI", "values": ["system-tests"]}])).ids

    # Loop through AMIs and delete the ones that meet the conditions
    for ami_id in ami_ids:
        print(" ")
        print(f"🔍 Checking AMI: {ami_id}")
        ami = await aws.ec2.get_ami(
            filters=[aws.ec2.GetAmiIdsFilterArgs(name="image-id", values=[ami_id])],
            owners=["self"],
            most_recent=True,
        )
        creation_date = datetime.fromisoformat(ami.creation_date.replace("Z", "+00:00"))

        # Fetch last launched time using AWS CLI
        last_launched_date = get_last_launched_time(ami_id)

        print(f"📅 AMI {ami.id} was created on {creation_date} and last launched data {last_launched_date}")

        # Check deletion conditions
        should_delete = False

        if creation_date < cutoff_creation_date:
            should_delete = True
            print(f"🕒 AMI {ami.id} is older than {ami_retention_days} days (Created on {creation_date})")

        if last_launched_date and last_launched_date < cutoff_last_launched_date:
            should_delete = True
            print(
                f"🚀 AMI {ami.id} not launched in the last {ami_last_launched_days} days (Last: {last_launched_date})"
            )

        if not last_launched_date and creation_date < cutoff_creation_date:
            should_delete = True
            print(
                f"❌ AMI {ami.id} was NEVER launched.(Older than {ami_retention_days} days created on {creation_date})"
            )

        # If conditions are met, delete AMI and its associated snapshots
        if should_delete:
            delete_ami(ami)
        else:
            print(f"✅ AMI {ami.id} is not eligible for deletion")


async def clean_up_amis_by_name() -> None:
    """Finds and deletes AMIs based on name pattern and tag CI:system-tests."""

    config = Config()
    ami_name = config.get("ami_name", None)
    ami_lang = config.get("ami_lang", None)
    print(f"🔍 Cleaning up AMIs by name [{ami_name}] and lang [{ami_lang}]")
    # Fetch all AMIs owned by this AWS account
    ami_ids = (await aws.ec2.get_ami_ids(owners=["self"], filters=[{"name": "tag:CI", "values": ["system-tests"]}])).ids
    for ami_id in ami_ids:
        ami = await aws.ec2.get_ami(
            filters=[aws.ec2.GetAmiIdsFilterArgs(name="image-id", values=[ami_id])],
            owners=["self"],
            most_recent=True,
        )
        name = ami.name
        if ami_name and ami_lang:
            # Both patterns must be in the name
            if ami_name in name and ami_lang in name:
                delete_ami(ami)
        elif (ami_name and ami_name in name) or (ami_lang and ami_lang in name):
            delete_ami(ami)


async def clean_up_ec2_running_instances() -> None:
    """Delete the ec2 instances that are running for more than x minutes"""
    print("🔍 Cleaning up EC2 instances")
    config = Config()
    ec2_age_minutes = int(config.require("ec2_age_minutes"))
    # Fetch all EC2 instances (not filtered by state)
    instances = await aws.ec2.get_instances(
        filters=[
            aws.ec2.GetInstancesFilterArgs(name="tag:CI", values=["system-tests"]),
            aws.ec2.GetInstancesFilterArgs(name="instance-state-name", values=["running"]),
        ]
    )

    now = datetime.now(UTC)
    for instance in instances.ids:
        print("Checking instance: ", instance)
        launch_time = get_instance_launch_time(instance)
        if launch_time:
            launch_time_parsed = datetime.strptime(launch_time, "%Y-%m-%dT%H:%M:%S%z")
            age = now - launch_time_parsed
            if age > timedelta(minutes=ec2_age_minutes):
                pulumi.log.info(f"💀 Terminating instance {instance} (age: {age})")
                command.local.Command(
                    f"terminate-{instance}", create=f"aws ec2 terminate-instances --instance-ids {instance} "
                )
        else:
            print(f"⚠️ Skipping instance {instance} — launch_time is None")


def create_pulumi_stack(program: Callable[[], Coroutine[Any, Any, None]]) -> auto.Stack:
    stack = None
    stack_name = "system-tests_onboarding_cleanup"
    project_name = "system-tests-vms"
    stack = auto.create_or_select_stack(stack_name=stack_name, project_name=project_name, program=program)
    if os.getenv("ONBOARDING_LOCAL_TEST") is None:
        stack.set_config("aws:SkipMetadataApiCheck", auto.ConfigValue("false"))
    return stack


def clean_up_amis_stack_up(ami_retention_days: int, ami_last_launched_days: int) -> None:
    stack = create_pulumi_stack(clean_up_amis)
    stack.set_config("ami_retention_days", auto.ConfigValue(str(ami_retention_days)))
    stack.set_config("ami_last_launched_days", auto.ConfigValue(str(ami_last_launched_days)))
    stack.up(on_output=print)
    stack.destroy(on_output=print, debug=True)


def clean_up_amis_by_name_stack_up(ami_name: str, ami_lang: str) -> None:
    if not ami_name and not ami_lang:
        raise ValueError("To delete amis by name you need to specify a name or a lang")
    stack = create_pulumi_stack(clean_up_amis_by_name)
    if ami_name:
        stack.set_config("ami_name", auto.ConfigValue(ami_name))
    if ami_lang:
        stack.set_config("ami_lang", auto.ConfigValue(ami_lang))
    stack.up(on_output=print)
    stack.destroy(on_output=print, debug=True)


def clean_up_ec2_stack_up(ec2_age_minutes: int = 45) -> None:
    stack = create_pulumi_stack(clean_up_ec2_running_instances)
    stack.set_config("ec2_age_minutes", auto.ConfigValue(str(ec2_age_minutes)))
    stack.up(on_output=print)
    stack.destroy(on_output=print, debug=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="get-pulumi-cleanup-parameters", description="Get scenarios and weblogs to run"
    )
    parser.add_argument(
        "--component",
        type=str,
        help="AWS component to clean up",
        choices=["amis", "amis_by_name", "amis_count", "ec2"],
    )

    parser.add_argument(
        "--ami-retention-days", type=int, help="Num of days to retain AMIs", default=DEFAULT_AMI_RETENTION_DAYS
    )

    parser.add_argument(
        "--ami-last-launched-days",
        type=int,
        help="Num of days since last launched",
        default=DEFAULT_AMI_LAST_LAUNCHED_DAYS,
    )

    parser.add_argument(
        "--ec2-age-minutes",
        type=int,
        help="Delete the ec2 instances that are running for more than x minutes",
        default=DEFAULT_AMI_RETENTION_DAYS,
    )

    parser.add_argument("--ami-name", type=str, help="Part of the name that we want to delete")
    parser.add_argument("--ami-lang", type=str, help="Lang pattern to remove amis")
    args = parser.parse_args()
    if args.component == "amis":
        clean_up_amis_stack_up(args.ami_retention_days, args.ami_last_launched_days)
    elif args.component == "amis_by_name":
        clean_up_amis_by_name_stack_up(args.ami_name, args.ami_lang)
    elif args.component == "ec2":
        clean_up_ec2_stack_up(args.ec2_age_minutes)
    elif args.component == "amis_count":
        number_of_amis = count_system_tests_amis()
        print(f"Number of AMIs with system-tests tag: {number_of_amis}")
        send_amis_count_to_datadog(number_of_amis)
    else:
        print(f"Invalid component: {args.component}")
        raise ValueError(f"Invalid component: {args.component}")
