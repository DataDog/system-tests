# Understanding the Provision System in AWS SSI Tests

## Overview

The provision system is a core component of the AWS SSI (Single Step Instrumentation) tests in system-tests. It allows you to define software installations, configuration changes, and commands to be executed on virtual machines in a structured and reproducible way.

![Provision Flow](../lib-injection/provision_flow.png "Provision Flow")

There are two types of provisions:

1. **Scenario Provisions**: These are the base installations needed for a test scenario (like the agent and Docker installation)
2. **Weblog Provisions**: These define how to install and run the test applications (weblogs)

Both types of provisions work together to create a complete testing environment:
- Scenario provisions setup the infrastructure (located at `utils/build/virtual_machine/provisions/[provision_name]/provision.yml`)
- Weblog provisions install and run the application to be tested (located at `utils/build/virtual_machine/weblogs/[lang]/provision_[weblog].yml`)

## Scenario Provision Structure

Scenario provisions are referenced in the scenario declaration in `utils/_context/_scenarios/__init__.py` or `utils/_context/_scenarios/auto_injection.py` via the `vm_provision` parameter. These YAML files have the following main sections:

### 1. init-environment (Optional)

This section defines environment variables that will be available during the installation process. Variables are defined per environment (dev/prod) and are prefixed with `DD_` when accessed in commands.

```yaml
init-environment:
  - env: dev  # Variables used when --vm-env=dev
    agent_repo_url: datad0g.com
    agent_dist_channel: beta
    agent_major_version: "apm"

  - env: prod  # Variables used when --vm-env=prod
    agent_repo_url: datadoghq.com
    agent_dist_channel: stable
    agent_major_version: "7"
```

When these variables are used in commands, they are accessed using the `$DD_` prefix. For example, `$DD_agent_repo_url` would contain `datad0g.com` in the dev environment.

### 2. tested_components (Mandatory)

This section defines commands that extract version information from the installed components. The output must be a valid JSON string with component name/version pairs.

```yaml
tested_components:
  install:
    - os_type: linux
      os_distro: rpm
      remote-command: |
          echo "{'agent':'$(rpm -qa --queryformat '%{VERSION}-%{RELEASE}' datadog-agent)'}"
    
    - os_type: linux
      os_distro: deb
      remote-command: |
          version_agent=$((dpkg -s datadog-agent || true) | grep Version | head -n 1) && \
          echo "{'agent':'${version_agent//'Version:'/}'}"
```

The JSON output from this section will be saved in the `tested_components.log` file and used to report which component versions were actually tested.

### 3. provision_steps (Mandatory)

This section defines the sequence of installation steps. Each entry references a step defined elsewhere in the file.

```yaml
provision_steps:
  - init-config       # First step to execute
  - install-docker    # Second step to execute
  - install-agent     # Third step to execute
```

The system follows this order exactly, so make sure dependencies between steps are handled properly.

### 4. Installation Steps

Each step mentioned in `provision_steps` should be defined with an `install` section that contains the commands to execute.

```yaml
init-config:
  cache: true  # If true, this step can be cached for faster execution
  install:
    - os_type: linux
      remote-command: echo "Initializing configuration..."
```

The `cache` option can be used to speed up repeated runs by skipping successful steps on subsequent executions.

## Weblog Provision Structure

Weblog provisions are simpler than scenario provisions and have a different structure. They are determined by the `--vm-weblog` and `--vm-library` command-line parameters, which specify which file to use (`provision_[weblog-name].yml`) and from which language folder to load it.

Weblog provisions have only two main sections:

### 1. lang_variant (Optional)

This section is **only required for host-based applications** where you need to install the programming language runtime on the host. For containerized applications, this section is not needed because the language runtime is included in the container.

Example for installing Java:

```yaml
lang_variant:
    name: DefaultJDK
    version: default
    cache: true
    install:
      - os_type: linux
        os_distro: deb
        remote-command: sudo apt-get -y update && sudo apt-get -y install default-jdk

      - os_type: linux
        os_distro: rpm
        remote-command: sudo dnf -y install java-devel || sudo yum -y install java-devel
```

### 2. weblog (Mandatory)

This section defines how to install, configure, and run the actual application. It follows the same structure as the installation steps in scenario provisions:

```yaml
weblog:
    name: test-app-java  # Should match the weblog name used in --vm-weblog
    install:
      - os_type: linux
        copy_files:
          - name: copy-service
            local_path: utils/build/virtual_machine/weblogs/common/test-app.service
          # ... other files to copy
        remote-command: sh test-app-java_run.sh
```

The `name` field should match the weblog name used in the `--vm-weblog` parameter.

### Differences Between Host-Based and Container-Based Weblogs

1. **Host-based weblogs**:
   - Usually include the `lang_variant` section to install the language runtime
   - Set up the application to run directly on the host
   - Typically run as a system service named `test-app-service`

2. **Container-based weblogs**:
   - Often omit the `lang_variant` section (the container includes the runtime)
   - Set up Docker containers to run the application
   - Use Docker commands in the `remote-command` section

## Installation Commands

Each installation section (in both scenario and weblog provisions) can contain three types of operations:

### 1. remote-command

Commands executed on the remote virtual machine.

```yaml
install-agent:
  install:
    - os_type: linux
      remote-command: |
        REPO_URL=$DD_agent_repo_url \
        DD_AGENT_DIST_CHANNEL=$DD_agent_dist_channel \
        DD_AGENT_MAJOR_VERSION=$DD_agent_major_version \
        bash -c "$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script_agent7.sh)"
```

Multi-line commands are supported using the YAML block syntax (`|`), which is perfect for complex installation scripts.

### 2. local-command

Commands executed on your local machine. These are useful for preparing files or other resources before copying them to the remote machine.

```yaml
prepare-files:
  install:
    - os_type: linux
      local-command: echo "Preparing files locally..."
```

### 3. copy_files

Copies files from your local machine to the remote virtual machine. This operation is critical for transferring application files, configuration files, or service definitions.

```yaml
setup-service:
  install:
    - os_type: linux
      copy_files:
        - name: copy-service-file
          local_path: utils/build/test.service
      remote-command: |
        sudo mv test.service /etc/systemd/system/
        sudo systemctl daemon-reload
```

Files are copied to the remote user's home directory by default. You can then move them to their final location using a `remote-command`.

## Cross-Platform Targeting

One of the most powerful features of the provision system is the ability to target specific operating systems, distributions, or architectures:

```yaml
install-prerequisites:
  install:
    # For Debian-based systems
    - os_type: linux
      os_distro: deb
      remote-command: |
        sudo apt-get update
        sudo apt-get install -y curl wget

    # For RPM-based systems
    - os_type: linux
      os_distro: rpm
      remote-command: |
        sudo yum install -y curl wget
        
    # For ARM64 architecture on Debian
    - os_type: linux
      os_distro: deb
      os_cpu: arm64
      remote-command: |
        # ARM64-specific commands
        
    # For specific OS branch (like Debian)
    - os_type: linux
      os_distro: deb
      os_branch: debian
      remote-command: |
        # Debian-specific commands
```

This allows you to write a single provision file that works across many different environments, which is essential for comprehensive testing.

Available targeting options:
- `os_type`: Operating system type (e.g., `linux`, `windows`)
- `os_distro`: Linux distribution type (e.g., `deb`, `rpm`)
- `os_cpu`: CPU architecture (e.g., `amd64`, `arm64`)
- `os_branch`: Distribution branch or version (e.g., `ubuntu20`, `ubuntu22_arm64`, `debian`)

## Complete Examples

### Scenario Provision Example

```yaml
# Optional: Load environment variables
init-environment:
  - env: dev
    agent_repo_url: datad0g.com
    agent_dist_channel: beta
    agent_major_version: "apm"
  - env: prod
    agent_repo_url: datadoghq.com
    agent_dist_channel: stable
    agent_major_version: "7"

# Mandatory: Extract component versions
tested_components:
  install:
    - os_type: linux
      os_distro: rpm
      remote-command: |
          echo "{'agent':'$(rpm -qa --queryformat '%{VERSION}-%{RELEASE}' datadog-agent)', 'docker':'$(docker --version | cut -d' ' -f3 | sed 's/,//')'}"
    - os_type: linux
      os_distro: deb
      remote-command: |
          version_agent=$((dpkg -s datadog-agent || true) | grep Version | head -n 1)
          docker_version=$(docker --version | cut -d' ' -f3 | sed 's/,//')
          echo "{'agent':'${version_agent//'Version:'/}', 'docker':'$docker_version'}"

# Mandatory: Define installation steps
provision_steps:
  - init-config
  - install-docker
  - install-agent

# Step 1: Initialize configuration
init-config:
  cache: true
  install:
    - os_type: linux
      remote-command: |
        echo "Setting up configuration..."
        mkdir -p /tmp/datadog-setup

# Step 2: Install Docker
install-docker:
  cache: true
  install:
    # For Debian-based systems
    - os_type: linux
      os_distro: deb
      remote-command: |
        sudo apt-get update
        sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
        sudo add-apt-repository "deb [arch=$(dpkg --print-architecture)] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
        sudo apt-get update
        sudo apt-get install -y docker-ce
        sudo systemctl start docker
        sudo systemctl enable docker
        sudo usermod -aG docker $USER
        
    # For RPM-based systems
    - os_type: linux
      os_distro: rpm
      remote-command: |
        sudo yum install -y yum-utils
        sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        sudo yum install -y docker-ce docker-ce-cli containerd.io
        sudo systemctl start docker
        sudo systemctl enable docker
        sudo usermod -aG docker $USER

# Step 3: Install Datadog Agent
install-agent:
  install:
    - os_type: linux
      copy_files:
        - name: copy-agent-config
          local_path: utils/build/datadog.yaml
      remote-command: |
        # Install the Datadog Agent
        REPO_URL=$DD_agent_repo_url \
        DD_AGENT_DIST_CHANNEL=$DD_agent_dist_channel \
        DD_AGENT_MAJOR_VERSION=$DD_agent_major_version \
        DD_API_KEY=$DD_API_KEY_ONBOARDING \
        bash -c "$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script_agent7.sh)"
        
        # Configure the agent
        sudo mv datadog.yaml /etc/datadog-agent/datadog.yaml
        sudo systemctl restart datadog-agent
```

### Weblog Provision Example (Host-based)

```yaml
# Optional: Install language runtime (for host-based applications)
lang_variant:
    name: DefaultJDK
    version: default
    cache: true
    install:
      - os_type: linux
        os_distro: deb
        os_branch: debian
        remote-command: |
          echo 'deb http://deb.debian.org/debian unstable main non-free contrib' | sudo tee -a /etc/apt/sources.list
          sudo apt update
          sudo apt -y install default-jdk
          
      - os_type: linux
        os_distro: deb
        remote-command: sudo apt-get -y update && sudo apt-get -y install default-jdk

      - os_type: linux
        os_distro: rpm
        remote-command: | 
          sudo yum install tar -y || sudo dnf install tar -y || true
          sudo sudo dnf -y install java-devel || sudo yum -y install java-devel

# Mandatory: Install and run the application
weblog:
    name: test-app-java
    install:
      - os_type: linux
        copy_files:
          - name: copy-service
            local_path: utils/build/virtual_machine/weblogs/common/test-app.service
          - name: copy-service-run-script
            local_path: utils/build/virtual_machine/weblogs/common/create_and_run_app_service.sh
          - name: copy-compile-weblog-script
            local_path: utils/build/virtual_machine/weblogs/java/test-app-java/compile_app.sh
          - name: copy-run-weblog-script
            local_path: utils/build/virtual_machine/weblogs/java/test-app-java/test-app-java_run.sh
          - name: copy-java-app
            local_path: lib-injection/build/docker/java/jetty-app
        remote-command: sh test-app-java_run.sh
```

### Weblog Provision Example (Container-based)

```yaml
# No lang_variant section needed for container-based applications

weblog:
    name: test-app-java-container
    install:
      - os_type: linux
        copy_files:
          - name: copy-run-script
            local_path: utils/build/virtual_machine/weblogs/java/test-app-java-container/run_container.sh
          - name: copy-dockerfile
            local_path: utils/build/virtual_machine/weblogs/java/test-app-java-container/Dockerfile
          - name: copy-java-app
            local_path: lib-injection/build/docker/java/jetty-app
        remote-command: |
          cd jetty-app
          sudo docker build -t test-app-java .
          sudo docker run -d --name test-app-java-container -p 8080:8080 test-app-java
          # Wait for container to be ready
          sleep 5
          # Check if it's running
          sudo docker ps | grep test-app-java-container
```

## Troubleshooting Common Issues

### 1. Wrong JSON format in tested_components

If your `tested_components` section produces invalid JSON, the system won't be able to report the tested component versions.

**Problem:**
```yaml
tested_components:
  install:
    - os_type: linux
      remote-command: |
          echo "agent: $(docker --version)"  # Not valid JSON!
```

**Solution:**
Ensure your output is properly formatted as a JSON string:
```yaml
tested_components:
  install:
    - os_type: linux
      remote-command: |
          echo "{'agent': '$(docker --version | sed -e 's/Docker version //' -e 's/,.*//')'}"
```

### 2. Environment variables not available

Variables defined in `init-environment` are available in commands with the `DD_` prefix.

**Problem:**
```yaml
install-agent:
  install:
    - os_type: linux
      remote-command: |
        echo "Using $agent_repo_url"  # Won't work!
```

**Solution:**
Use the proper prefix:
```yaml
install-agent:
  install:
    - os_type: linux
      remote-command: |
        echo "Using $DD_agent_repo_url"  # Correct
```

### 3. OS-specific code not running

If your OS-specific code isn't running, check that you've correctly specified `os_type`, `os_distro`, and `os_cpu`.

**Problem:**
Specified an incorrect or missing OS property.

**Solution:**
Add debug commands to verify the OS detection:
```yaml
debug-os:
  install:
    - os_type: linux
      remote-command: |
        echo "OS: $(uname -a)"
        echo "Distribution: $(cat /etc/os-release | grep -E '^ID=' | cut -d= -f2)"
        echo "Architecture: $(uname -m)"
```

### 4. File copying fails

If `copy_files` operations fail, check that the local path is correct.

**Problem:**
Incorrect local path:
```yaml
setup-service:
  install:
    - os_type: linux
      copy_files:
        - name: copy-service
          local_path: service/file.txt  # Wrong path
```

**Solution:**
Verify that the file exists and the path is relative to the system-tests root:
```yaml
setup-service:
  install:
    - os_type: linux
      copy_files:
        - name: copy-service
          local_path: utils/build/service/file.txt  # Correct path
```

### 5. Host-based weblog service not starting

For host-based weblogs, the application should run as a system service.

**Problem:**
Service not starting or not being found.

**Solution:**
Check that your service is properly installed and enabled:
```yaml
weblog:
    name: test-app-service-check
    install:
      - os_type: linux
        remote-command: |
          # Check service installation
          ls -la /etc/systemd/system/test-app-service.service
          # Check service status
          sudo systemctl status test-app-service || true
          # Try to restart service if it failed
          sudo systemctl restart test-app-service
          # Enable service for automatic start
          sudo systemctl enable test-app-service
```

## Quick Start Templates

### Minimal Scenario Provision Template

```yaml
# Environment variables
init-environment:
  - env: dev
    MY_VAR: dev_value
  - env: prod
    MY_VAR: prod_value

# Component version detection
tested_components:
  install:
    - os_type: linux
      remote-command: |
          echo "{'my_component':'1.0.0'}"

# Installation steps
provision_steps:
  - setup-environment
  - install-components

# Define steps
setup-environment:
  cache: true
  install:
    - os_type: linux
      remote-command: echo "Setting up environment with $DD_MY_VAR"

install-components:
  install:
    - os_type: linux
      remote-command: echo "Installing components..."
```

### Minimal Host-Based Weblog Template

```yaml
# Optional: Install language runtime
lang_variant:
    name: MyLanguageRuntime
    version: default
    cache: true
    install:
      - os_type: linux
        os_distro: deb
        remote-command: sudo apt-get install -y my-language

      - os_type: linux
        os_distro: rpm
        remote-command: sudo yum install -y my-language

# Mandatory: Install and run application
weblog:
    name: my-app
    install:
      - os_type: linux
        copy_files:
          - name: copy-service
            local_path: utils/build/virtual_machine/weblogs/common/test-app.service
          - name: copy-app
            local_path: path/to/my/app
        remote-command: |
          # Set up application
          cd my-app
          # Install application as service
          sudo mv ../test-app.service /etc/systemd/system/
          sudo systemctl daemon-reload
          sudo systemctl start test-app-service
```

### Minimal Container-Based Weblog Template

```yaml
# No lang_variant needed for container-based weblog

weblog:
    name: my-container-app
    install:
      - os_type: linux
        copy_files:
          - name: copy-dockerfile
            local_path: path/to/Dockerfile
          - name: copy-app
            local_path: path/to/app
        remote-command: |
          # Build and run container
          sudo docker build -t my-app .
          sudo docker run -d --name my-app-container -p 8080:8080 my-app
```

## Best Practices

1. **Make provisions idempotent**: Ensure scripts can be run multiple times without error
2. **Use package managers when possible**: They handle dependencies better than manual installations
3. **Keep provision steps small and focused**: This makes debugging easier
4. **Test across multiple OS types and distributions**: Your provision should work on all supported platforms
5. **Use environment variables for configuration**: This makes provisions more flexible
6. **Validate output JSON in tested_components**: Ensure it's properly escaped and formatted
7. **Handle failure gracefully**: Add fallbacks and error checking to your commands
8. **For host-based weblogs, use system services**: Run applications as system services for better reliability
9. **For container-based weblogs, use proper Docker practices**: Use --name for containers, proper port mapping, etc.
10. **Document your provision**: Add comments to explain complex operations
