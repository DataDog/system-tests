#!/usr/bin/env python3
"""
Kind Cluster Setup Troubleshooting Script

This script extracts the kind cluster setup logic from the system-tests
to help troubleshoot CI environment issues, particularly for migration
from local Docker daemon to tcp://docker:2375.

Usage:
    python troubleshoot_kind_setup.py [--cleanup]

Environment Variables:
    DOCKER_HOST - Set to tcp://docker:2375 for remote Docker daemon
    CI - Set to enable CI-specific configurations
    GITLAB_CI - Set to enable GitLab-specific setup
"""

import os
import sys
import time
import subprocess
import shlex
import re
import tempfile
import argparse
from pathlib import Path


def log(message, level="INFO"):
    """Simple logging function"""
    print(f"[{level}] {message}")


def execute_command(command, timeout=90, quiet=False):
    """Execute shell command with timeout and logging"""
    log(f"Executing: {command}")

    try:
        process = subprocess.Popen(
            shlex.split(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )

        output, _ = process.communicate(timeout=timeout)

        if not quiet:
            log(f"Output:\n{output}")

        if process.returncode != 0:
            raise Exception(f"Command failed with return code {process.returncode}: {output}")

        return output.strip()

    except subprocess.TimeoutExpired:
        process.kill()
        raise Exception(f"Command timed out after {timeout} seconds: {command}")
    except Exception as e:
        log(f"Command failed: {e}", "ERROR")
        raise


def check_prerequisites():
    """Check if required tools are available"""
    log("Checking prerequisites...")

    required_tools = ["kind", "kubectl", "docker"]
    missing_tools = []

    for tool in required_tools:
        try:
            execute_command(f"which {tool}", quiet=True)
            log(f"✓ {tool} found")
        except:
            missing_tools.append(tool)
            log(f"✗ {tool} not found", "ERROR")

    if missing_tools:
        log(f"Missing required tools: {missing_tools}", "ERROR")
        sys.exit(1)

    # Check Docker connectivity
    try:
        docker_info = execute_command("docker info", quiet=True)
        log("✓ Docker daemon accessible")
        if "DOCKER_HOST" in os.environ:
            log(f"  Using DOCKER_HOST: {os.environ['DOCKER_HOST']}")
    except Exception as e:
        log(f"✗ Docker daemon not accessible: {e}", "ERROR")
        sys.exit(1)


def create_kind_config():
    """Create appropriate kind configuration based on environment"""
    log("Creating kind configuration...")

    # Determine if we're in CI environment
    is_ci = "CI" in os.environ
    log(f"CI environment detected: {is_ci}")

    if is_ci:
        config_content = """kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
# Complete CI config for Docker-in-Docker runners
networking:
  ipFamily: ipv4
  apiServerAddress: "0.0.0.0"
nodes:
  - role: control-plane
    extraPortMappings:
      # agent port - accessible from all interfaces in CI
      - containerPort: 8126
        hostPort: 8127
        listenAddress: "0.0.0.0"
        protocol: TCP
      # app port - accessible from all interfaces in CI
      - containerPort: 18080
        hostPort: 18081
        listenAddress: "0.0.0.0"
        protocol: TCP
kubeadmConfigPatches:
  - |
    kind: ClusterConfiguration
    apiServer:
      certSANs:
        - "docker"
        - "localhost"
        - "0.0.0.0"
"""
    else:
        config_content = """kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraPortMappings:
      # agent port
      - containerPort: 8126
        hostPort: 8127
        listenAddress: "127.0.0.1"
        protocol: TCP
      # app port
      - containerPort: 18080
        hostPort: 18081
        listenAddress: "127.0.0.1"
        protocol: TCP
"""

    # Write config to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        config_file = f.name

    log(f"Kind config written to: {config_file}")
    log(f"Config content:\n{config_content}")

    return config_file


def create_kind_cluster(config_file):
    """Create the kind cluster"""
    cluster_name = "lib-injection-testing"
    log(f"Creating kind cluster: {cluster_name}")

    # Check if cluster already exists
    try:
        existing_clusters = execute_command("kind get clusters", quiet=True)
        if cluster_name in existing_clusters.split('\n'):
            log(f"Cluster {cluster_name} already exists, deleting it first...")
            execute_command(f"kind delete cluster --name {cluster_name}")
    except:
        pass

    # Create the cluster
    kind_command = f"kind create cluster --image=kindest/node:v1.25.3@sha256:f52781bc0d7a19fb6c405c2af83abfeb311f130707a0e219175677e366cc45d1 --name {cluster_name} --config {config_file} --wait 1m"

    try:
        execute_command(kind_command, timeout=300)  # 5 minutes timeout
        log("✓ Kind cluster created successfully")
    except Exception as e:
        log(f"✗ Failed to create kind cluster: {e}", "ERROR")
        return False

    return True


def verify_kubeconfig():
    """Verify kubeconfig is properly set up"""
    log("Verifying kubeconfig...")

    kubeconfig_path = os.path.expanduser("~/.kube/config")

    if not os.path.exists(kubeconfig_path):
        log(f"✗ Kubeconfig not found at {kubeconfig_path}", "ERROR")
        return False

    # Show kubeconfig content
    with open(kubeconfig_path, 'r') as f:
        content = f.read()

    log("Current kubeconfig:")
    print(content)

    # Check server URLs
    server_lines = [line for line in content.split('\n') if 'server:' in line]
    for line in server_lines:
        log(f"Found server: {line.strip()}")

    return True


def fix_kubeconfig_for_ci():
    """Apply CI-specific kubeconfig fixes"""
    if "CI" not in os.environ:
        log("Not in CI environment, skipping kubeconfig fixes")
        return

    log("Applying CI-specific kubeconfig fixes...")

    try:
        kubeconfig_path = os.path.expanduser("~/.kube/config")

        # Read current kubeconfig
        with open(kubeconfig_path, 'r') as f:
            kubeconfig_content = f.read()

        log("Original kubeconfig server URLs:")
        server_lines = [line for line in kubeconfig_content.split('\n') if 'server:' in line]
        for line in server_lines:
            log(f"  {line.strip()}")

        # Save original for debugging
        with open("original-kubeconfig.yaml", 'w') as f:
            f.write(kubeconfig_content)
        log("Original kubeconfig saved to original-kubeconfig.yaml")

        # Replace various server URL patterns with docker hostname
        patterns_to_fix = [
            (r'(\s+server:\s+https://)localhost(:[\d]+)', r'\1docker\2'),
            (r'(\s+server:\s+https://)0\.0\.0\.0(:[\d]+)', r'\1docker\2'),
            (r'(\s+server:\s+https://)172\.17\.0\.\d+(:[\d]+)', r'\1docker\2'),
            (r'(\s+server:\s+https://)172\.18\.0\.\d+(:[\d]+)', r'\1docker\2'),
        ]

        fixed_content = kubeconfig_content
        for pattern, replacement in patterns_to_fix:
            old_content = fixed_content
            fixed_content = re.sub(pattern, replacement, fixed_content)
            if old_content != fixed_content:
                log(f"Applied fix: {pattern}")

        if fixed_content == kubeconfig_content:
            log("WARNING: No server URLs were modified!")

        # Write back the fixed kubeconfig
        with open(kubeconfig_path, 'w') as f:
            f.write(fixed_content)

        log("Fixed kubeconfig server URLs:")
        fixed_server_lines = [line for line in fixed_content.split('\n') if 'server:' in line]
        for line in fixed_server_lines:
            log(f"  {line.strip()}")

        # Save fixed version for debugging
        with open("fixed-kubeconfig.yaml", 'w') as f:
            f.write(fixed_content)
        log("Fixed kubeconfig saved to fixed-kubeconfig.yaml")

        log("✓ CI kubeconfig fixes applied successfully")

    except Exception as e:
        log(f"✗ Failed to apply CI kubeconfig fixes: {e}", "ERROR")
        return False

    return True


def setup_gitlab_networking():
    """Apply GitLab CI specific networking setup"""
    if "GITLAB_CI" not in os.environ:
        log("Not in GitLab CI environment, skipping GitLab setup")
        return True

    log("Applying GitLab CI specific networking setup...")

    try:
        cluster_name = "lib-injection-testing"

        # Get the correct control plane IP
        correct_control_plane_ip = execute_command(
            f"docker container inspect {cluster_name}-control-plane --format '{{{{.NetworkSettings.Networks.bridge.IPAddress}}}}'"
        ).strip()

        if not correct_control_plane_ip:
            raise Exception("Unable to find correct control plane IP")

        log(f"Found control plane IP: {correct_control_plane_ip}")

        # Get current control plane address from config
        control_plane_address_in_config = execute_command(
            f"docker container inspect {cluster_name}-control-plane --format '{{{{index .NetworkSettings.Ports \"6443/tcp\" 0 \"HostIp\"}}}}:{{{{index .NetworkSettings.Ports \"6443/tcp\" 0 \"HostPort\"}}}}'"
        ).strip()

        if not control_plane_address_in_config:
            raise Exception("Unable to find control plane address from config")

        log(f"Current control plane address in config: {control_plane_address_in_config}")

        # Replace server config with container IP + internal port
        execute_command(
            f"sed -i -e 's/{control_plane_address_in_config}/{correct_control_plane_ip}:6443/g' {os.environ['HOME']}/.kube/config"
        )

        log("✓ GitLab networking setup completed")
        return True

    except Exception as e:
        log(f"✗ Failed GitLab networking setup: {e}", "ERROR")
        return False


def test_cluster_connectivity():
    """Test various aspects of cluster connectivity"""
    log("Testing cluster connectivity...")

    tests = [
        ("kubectl cluster-info", "Basic cluster info"),
        ("kubectl get nodes", "Node status"),
        ("kubectl get namespaces", "Namespace access"),
        ("kubectl get pods --all-namespaces", "Pod listing"),
    ]

    results = []

    for command, description in tests:
        try:
            output = execute_command(command, quiet=True)
            log(f"✓ {description}")
            results.append((description, True, output))
        except Exception as e:
            log(f"✗ {description}: {e}", "ERROR")
            results.append((description, False, str(e)))

    return results


def test_port_connectivity():
    """Test if the mapped ports are accessible"""
    log("Testing port connectivity...")

    # Test if ports are mapped in kind container
    try:
        cluster_name = "lib-injection-testing"
        port_info = execute_command(
            f"docker port {cluster_name}-control-plane", quiet=True
        )
        log(f"Kind container port mappings:\n{port_info}")
    except Exception as e:
        log(f"Failed to get port info: {e}", "ERROR")

    # Test if we can reach the ports
    docker_host = os.environ.get("DOCKER_HOST", "")
    if "docker:" in docker_host:
        host_to_test = "docker"
    else:
        host_to_test = "localhost"

    log(f"Testing connectivity to {host_to_test}")

    ports_to_test = [8127, 18081]  # The external ports from kind config

    for port in ports_to_test:
        try:
            # Use curl to test HTTP connectivity (will fail but shows if port is open)
            execute_command(f"curl -m 5 {host_to_test}:{port}", quiet=True)
            log(f"✓ Port {port} is accessible")
        except:
            # Check if port is listening using netstat or ss
            try:
                execute_command(f"ss -tuln | grep :{port}", quiet=True)
                log(f"? Port {port} is listening (connection test failed)")
            except:
                log(f"✗ Port {port} not accessible", "ERROR")


def cleanup_cluster():
    """Clean up the test cluster"""
    log("Cleaning up kind cluster...")

    try:
        execute_command("kind delete cluster --name lib-injection-testing")
        log("✓ Cluster cleanup completed")
    except Exception as e:
        log(f"Cleanup failed: {e}", "ERROR")


def debug_docker_environment():
    """Debug Docker environment and networking"""
    log("=== Docker Environment Debug ===")

    debug_commands = [
        ("docker --version", "Docker version"),
        ("docker info", "Docker info"),
        ("docker network ls", "Docker networks"),
        ("docker ps --filter name=lib-injection", "Kind containers"),
    ]

    for command, description in debug_commands:
        try:
            log(f"\n--- {description} ---")
            output = execute_command(command, quiet=True)
            print(output)
        except Exception as e:
            log(f"Failed to get {description}: {e}", "ERROR")

    # Show environment variables
    log("\n--- Environment Variables ---")
    env_vars = ["DOCKER_HOST", "CI", "GITLAB_CI", "HOME", "KUBECONFIG"]
    for var in env_vars:
        value = os.environ.get(var, "Not set")
        log(f"{var}: {value}")


def main():
    parser = argparse.ArgumentParser(description="Troubleshoot kind cluster setup for CI")
    parser.add_argument("--cleanup", action="store_true", help="Only cleanup existing cluster")
    parser.add_argument("--debug-only", action="store_true", help="Only run debug commands")

    args = parser.parse_args()

    log("=== Kind Cluster Troubleshooting Script ===")

    if args.debug_only:
        debug_docker_environment()
        return

    if args.cleanup:
        cleanup_cluster()
        return

    try:
        # Debug environment first
        debug_docker_environment()

        # Check prerequisites
        check_prerequisites()

        # Create and apply kind configuration
        config_file = create_kind_config()

        # Create the cluster
        if not create_kind_cluster(config_file):
            sys.exit(1)

        # Verify kubeconfig
        if not verify_kubeconfig():
            sys.exit(1)

        # Apply CI fixes
        if not fix_kubeconfig_for_ci():
            sys.exit(1)

        # Apply GitLab networking
        if not setup_gitlab_networking():
            sys.exit(1)

        # Test connectivity
        test_results = test_cluster_connectivity()
        test_port_connectivity()

        log("=== Summary ===")
        for description, success, output in test_results:
            status = "✓" if success else "✗"
            log(f"{status} {description}")

        # Clean up config file
        os.unlink(config_file)

        log("=== Troubleshooting completed ===")
        log("Cluster is ready for testing. Use 'python troubleshoot_kind_setup.py --cleanup' to remove it.")

    except KeyboardInterrupt:
        log("Script interrupted by user", "ERROR")
        sys.exit(1)
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
