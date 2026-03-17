#!/usr/bin/env python3
"""Script to update K8s pinned versions by extracting versions from Docker images."""

import sys
from pathlib import Path

import requests

# Add the repository root to the Python path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))

from utils.k8s.k8s_component_image import K8sComponentImage, extract_cluster_agent_version  # noqa: E402
from utils.k8s.k8s_components_parser import K8sComponentsParser  # noqa: E402

# Version tags that indicate non-stable releases
NON_STABLE_VERSION_TAGS = ["dev", "rc", "alpha", "beta", "snapshot"]


def _is_stable_version(version: str) -> bool:
    """Check if a version string represents a stable release."""
    return not any(tag in version.lower() for tag in NON_STABLE_VERSION_TAGS)


def _get_latest_stable_version_from_artifacthub(package_name: str) -> str:
    """Get the latest stable version from an Artifact Hub Helm package."""
    url = f"https://artifacthub.io/api/v1/packages/helm/datadog/{package_name}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()
    available_versions = data.get("available_versions", [])

    # Find the first stable version
    for version_info in available_versions:
        version = version_info["version"]
        if _is_stable_version(version):
            return version

    # Fallback to main version field
    main_version = data.get("version", "")
    if main_version and _is_stable_version(main_version):
        return main_version

    raise ValueError(f"No stable version found for {package_name} in Artifact Hub")


def get_datadog_operator_latest_version() -> str:
    """Extract the latest stable Datadog Operator version from Artifact Hub."""
    return _get_latest_stable_version_from_artifacthub("datadog-operator")


def get_datadog_helm_chart_latest_version() -> str:
    """Extract the latest stable Datadog Helm chart version from Artifact Hub."""
    return _get_latest_stable_version_from_artifacthub("datadog")


def get_cluster_agent_version(registry_url: str = "public.ecr.aws/datadog/cluster-agent:latest") -> str:
    """Extract the cluster agent version from a Docker image."""
    cluster_agent_image = K8sComponentImage(registry_url=registry_url, version_extractor=extract_cluster_agent_version)
    return cluster_agent_image.version


def main() -> int:
    """Extract and print K8s component versions.

    Returns:
        0 if updates were made, 1 if no updates were needed

    """
    parser = K8sComponentsParser()

    print("Fetching latest versions...")

    # Get the cluster agent version from public ECR
    cluster_agent_version = get_cluster_agent_version("public.ecr.aws/datadog/cluster-agent:latest")

    # Get the Datadog Operator version
    operator_version = get_datadog_operator_latest_version()

    # Get the Datadog Helm chart version
    helm_chart_version = get_datadog_helm_chart_latest_version()

    print("\nLatest versions found:")
    print(f"  Cluster Agent: {cluster_agent_version}")
    print(f"  Datadog Operator: {operator_version}")
    print(f"  Datadog Helm Chart: {helm_chart_version}")

    # Update pinned versions
    print("\nUpdating pinned versions...")

    # Build the full cluster agent pinned URL with the new version
    cluster_agent_pinned = f"235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/cluster-agent:{cluster_agent_version}"

    updates_made = False

    # Update cluster_agent
    if parser.update_pinned_version("cluster_agent", cluster_agent_pinned):
        print(f"  ✓ Updated cluster_agent to {cluster_agent_version}")
        updates_made = True
    else:
        print(f"  - cluster_agent already at {cluster_agent_version}")

    # Update helm_chart
    if parser.update_pinned_version("helm_chart", helm_chart_version):
        print(f"  ✓ Updated helm_chart to {helm_chart_version}")
        updates_made = True
    else:
        print(f"  - helm_chart already at {helm_chart_version}")

    # Update helm_chart_operator
    if parser.update_pinned_version("helm_chart_operator", operator_version):
        print(f"  ✓ Updated helm_chart_operator to {operator_version}")
        updates_made = True
    else:
        print(f"  - helm_chart_operator already at {operator_version}")

    if updates_made:
        print("\n✅ Pinned versions updated successfully in k8s_components.json")
        return 0  # Exit code 0 = changes made
    print("\n✅ All pinned versions are already up to date")
    return 1  # Exit code 1 = no changes


if __name__ == "__main__":
    sys.exit(main())
