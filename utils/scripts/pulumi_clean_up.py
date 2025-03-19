import os
import argparse
import subprocess
import json
import pulumi
import pulumi_aws as aws
from pulumi import automation as auto
from datetime import datetime, timedelta, UTC
from utils.tools import logger
from pulumi import Config

# Define retention settings
DEFAULT_AMI_RETENTION_DAYS = 100
DEFAULT_AMI_LAST_LAUNCHED_DAYS = 111
stack = None
stack_name = "system-tests_onboarding_cleanup"


def get_last_launched_time(ami_id) -> datetime:
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


def deregister_ami(ami_id) -> None:
    """Deregisters an AMI using AWS CLI."""
    try:
        subprocess.run(["aws", "ec2", "deregister-image", "--image-id", ami_id], check=True)
        pulumi.log.info(f"✅ Successfully deregistered AMI {ami_id}")
    except Exception as e:
        pulumi.log.warn(f"⚠️ Failed to deregister AMI {ami_id}: {e}")


def delete_snapshot(snapshot_id) -> None:
    """Deletes a snapshot using AWS CLI."""
    try:
        subprocess.run(["aws", "ec2", "delete-snapshot", "--snapshot-id", snapshot_id], check=True)
        pulumi.log.info(f"✅ Successfully deleted snapshot {snapshot_id}")
    except Exception as e:
        pulumi.log.warn(f"⚠️ Failed to delete snapshot {snapshot_id}: {e}")


async def clean_up_amis() -> None:
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
            print(f"🔥 Deleting AMI: {ami.id}")

            # Deregister the AMI using AWS CLI
            deregister_ami(ami.id)

            for block in ami.block_device_mappings:
                if "ebs" in block and "snapshot_id" in block["ebs"]:
                    snapshot_id = block["ebs"]["snapshot_id"]
                    pulumi.log.info(f"🗑️ Deleting snapshot: {snapshot_id}")
                    delete_snapshot(snapshot_id)

        else:
            print(f"✅ AMI {ami.id} is not eligible for deletion")


def clean_up_amis_stack_up(ami_retention_days: int, ami_last_launched_days: int) -> None:
    project_name = "system-tests-vms"
    stack = auto.create_or_select_stack(stack_name=stack_name, project_name=project_name, program=clean_up_amis)
    if os.getenv("ONBOARDING_LOCAL_TEST") is None:
        stack.set_config("aws:SkipMetadataApiCheck", auto.ConfigValue("false"))
    stack.set_config("ami_retention_days", auto.ConfigValue(str(ami_retention_days)))
    stack.set_config("ami_last_launched_days", auto.ConfigValue(str(ami_last_launched_days)))

    up_res = stack.up(on_output=print)
    print(f"🚀 Stack up result: {up_res}")
    stack.destroy(on_output=print, debug=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="get-pulumi-cleanup-parameters", description="Get scenarios and weblogs to run"
    )
    parser.add_argument(
        "--component",
        type=str,
        help="AWS component to clean up",
        choices=["amis", "ec2"],
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

    args = parser.parse_args()
    if args.component == "amis":
        clean_up_amis_stack_up(args.ami_retention_days, args.ami_last_launched_days)
    else:
        logger.error(f"Invalid component: {args.component}")
        raise ValueError(f"Invalid component: {args.component}")
