# K8s Injector Dev

## Introduction

The K8s Injector Dev scenarios are a set of test scenarios designed to test the Kubernetes library injection Datadog components that enable automatic instrumentation of pods. These scenarios validate the functionality of Datadog's auto-injection capabilities in Kubernetes environments.

These scenarios are based on the `injector-dev` tool, which provides a comprehensive suite of tools to support the auto_inject library functionality. At the moment, this tool primarily supports Kubernetes environments and focuses on testing the library injection mechanisms that automatically instrument applications running in Kubernetes pods without requiring manual code changes.

The scenarios help ensure that:
- Library injection works correctly across different Kubernetes configurations
- Auto-instrumentation is properly applied to target pods
- The injection process doesn't interfere with application functionality
- Datadog tracing and monitoring capabilities are successfully enabled

## Prerequisites

To run the K8s Injector Dev scenarios, you need to meet the following requirements:

### System-Tests Requirements

First, you must satisfy the standard system-tests requirements. For detailed information about these requirements, please refer to the [system-tests README](../README.md#minimal-requirements-end-to-end-testing).

### Injector-Dev Specific Requirements

In addition to the standard system-tests requirements, you need the following tools installed and configured for the injector-dev functionality:

- **injector-dev binary** (ESSENTIAL): The injector-dev binary is absolutely essential to run these test scenarios. You must place the binary in the `binaries/` folder of your system-tests workspace. To obtain the binary, you can either:
  - Download a pre-built binary from the [injector-dev repository](https://github.com/DataDog/injector-dev)
  - Build the binary manually following the instructions in the [injector-dev repository](https://github.com/DataDog/injector-dev)

- **Colima** (for the default colima platform)
- **MiniKube**
- **Helm**
- **Kubectl**

For more detailed information about the injector-dev tool and its setup, please visit the [injector-dev repository](https://github.com/DataDog/injector-dev).

## Running the Tests

There are two ways to run the K8s Injector Dev scenarios:

### Option 1: Using the Wizard (Recommended)

The easiest way to run these tests is using the interactive wizard script. This wizard automates the entire setup and execution process.

**Run the wizard:**
```bash
./utils/scripts/ssi_wizards/k8s_injector_dev_wizard.sh
```

**What the wizard does:**

1. **Binary Management**: Checks for the injector-dev binary in the `binaries/` folder and helps you obtain it if missing (from local path or download URL)

2. **Requirements Installation**: Automatically installs required tools (Colima, MiniKube, Helm, Kubectl) for your operating system

3. **Registry Configuration**: Configures Docker registry access with two options:
   - Use existing ECR registry (235494822917.dkr.ecr.us-east-1.amazonaws.com)
   - Configure your own private registry

4. **Test Selection**: Guides you through selecting:
   - **Scenario**: Currently supports `K8S_INJECTOR_DEV_SINGLE_SERVICE`
   - **Language**: Java, .NET, Node.js, Python, or Ruby
   - **Weblog**: Multiple test applications available per language (configured in `utils/scripts/ci_orchestrators/k8s_injector_dev.json`)

5. **Image Management**:
   - Builds and pushes weblog images to your private registry
   - Migrates public Datadog images (cluster-agent, apm-injector, lib-init) to your private registry if needed
   - Configures image tags and registry paths

6. **Test Execution**: Constructs and executes the final test command with all configured parameters

**Available Test Applications** (from the wizard configuration):
- **Java**: `dd-lib-java-init-test-app`
- **.NET**: `dd-lib-dotnet-init-test-app`
- **Node.js**: `sample-app`
- **Python**: Multiple Django variants including `dd-lib-python-init-test-django`, `dd-lib-python-init-test-django-gunicorn`, etc.
- **Ruby**: Rails variants including `dd-lib-ruby-init-test-rails`, `dd-lib-ruby-init-test-rails-explicit`, etc.

### Option 2: Manual Execution

You can also run the tests manually by providing all parameters directly to the run script. This approach gives you complete control over the test configuration.

#### Private Registry Configuration

K8s Injector Dev tests require a private Docker registry to store and access the test images. The private registry configuration is handled through environment variables. But you also have to perform the login manually before:

```bash
aws-vault exec sso-apm-ecosystems-reliability-account-admin -- aws ecr get-login-password | docker login --username AWS --password-stdin 235494822917.dkr.ecr.us-east-1.amazonaws.com
```

**Required Environment Variables:**

```bash
export PRIVATE_DOCKER_REGISTRY="<registry-url>"
export PRIVATE_DOCKER_REGISTRY_USER="<username>"
export PRIVATE_DOCKER_REGISTRY_TOKEN="<token-or-password>"
```

**Parameters:**

- **PRIVATE_DOCKER_REGISTRY**: The URL of your private Docker registry
  - Example: `235494822917.dkr.ecr.us-east-1.amazonaws.com` (ECR)
  - Example: `your-registry.com` (custom registry)

- **PRIVATE_DOCKER_REGISTRY_USER**: The username for registry authentication
  - For ECR: `AWS`
  - For custom registries: your specific username

- **PRIVATE_DOCKER_REGISTRY_TOKEN**: The authentication token/password
  - For ECR: Use `aws ecr get-login-password --region <region>`
  - For custom registries: your registry password or token

**How it works:**

1. The system validates that all three environment variables are properly set
2. During cluster setup, it creates a Kubernetes secret called `private-registry-secret` with the registry credentials
3. The default service account is patched to use this secret for pulling images from the private registry
4. All test images (weblog, cluster-agent, apm-injector, lib-init) are pulled from the configured private registry

**Example ECR Configuration:**

```bash
# Set registry configuration
export PRIVATE_DOCKER_REGISTRY="235494822917.dkr.ecr.us-east-1.amazonaws.com"
export PRIVATE_DOCKER_REGISTRY_USER="AWS"

# Option 1: Using aws-vault (recommended for Datadog ECR)
aws-vault exec sso-apm-ecosystems-reliability-account-admin -- aws ecr get-login-password | docker login --username AWS --password-stdin 235494822917.dkr.ecr.us-east-1.amazonaws.com
export PRIVATE_DOCKER_REGISTRY_TOKEN=$(aws-vault exec sso-apm-ecosystems-reliability-account-admin -- aws ecr get-login-password --region us-east-1)

# Option 2: Using direct AWS CLI (requires AWS credentials configured)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 235494822917.dkr.ecr.us-east-1.amazonaws.com
export PRIVATE_DOCKER_REGISTRY_TOKEN=$(aws ecr get-login-password --region us-east-1)
```

**Important Notes:**

- All injection images (cluster-agent, apm-injector, lib-init) must be available in the same registry path
- The wizard automatically handles image migration from public repositories to your private registry
- ECR tokens expire, so you may need to refresh the token for long-running tests

#### Command Line Parameters

Once you have configured the private registry environment variables, you can run the tests manually using the following command structure:

```bash
./run.sh <SCENARIO> --k8s-library <LIBRARY> --k8s-weblog <WEBLOG> --k8s-weblog-img <WEBLOG_IMAGE> --k8s-cluster-img <CLUSTER_AGENT_IMAGE> --k8s-lib-init-img <LIB_INIT_IMAGE> --k8s-injector-img <INJECTOR_IMAGE> --k8s-ssi-registry-base <REGISTRY_BASE>
```

**Required Parameters:**

- **SCENARIO**: The test scenario to run
  - Currently supported: `K8S_INJECTOR_DEV_SINGLE_SERVICE`

- **--k8s-library**: The programming language of the test library
  - Options: `java`, `dotnet`, `nodejs`, `python`, `ruby`

- **--k8s-weblog**: The weblog application to test
  - Varies by language (see available applications in wizard configuration)

- **--k8s-weblog-img**: Full path to the weblog image in your private registry
  - Format: `<registry>/<namespace>/<weblog>:<tag>`
  - Example: `235494822917.dkr.ecr.us-east-1.amazonaws.com/system-tests/dd-lib-java-init-test-app:latest`

- **--k8s-cluster-img**: Cluster agent image name and tag
  - Example: `cluster-agent:latest`

- **--k8s-lib-init-img**: Library initialization image name and tag
  - Language-specific examples:
    - Java: `dd-lib-java-init:latest`
    - .NET: `dd-lib-dotnet-init:latest`
    - Node.js: `dd-lib-js-init:latest`
    - Python: `dd-lib-python-init:latest`
    - Ruby: `dd-lib-ruby-init:latest`

- **--k8s-injector-img**: APM injector image name and tag
  - Example: `apm-inject:latest`

- **--k8s-ssi-registry-base**: Base registry path for all injection images
  - Format: `<registry>/<namespace>`
  - Example: `235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi`

**Complete Example:**

```bash
./run.sh K8S_INJECTOR_DEV_SINGLE_SERVICE \
  --k8s-library java \
  --k8s-weblog dd-lib-java-init-test-app \
  --k8s-weblog-img 235494822917.dkr.ecr.us-east-1.amazonaws.com/system-tests/dd-lib-java-init-test-app:latest \
  --k8s-cluster-img cluster-agent:latest \
  --k8s-lib-init-img dd-lib-java-init:latest \
  --k8s-injector-img apm-inject:latest \
  --k8s-ssi-registry-base 235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi
```

### Test Scenarios

The K8s Injector Dev tests currently support the following scenarios:

- **K8S_INJECTOR_DEV_SINGLE_SERVICE**: Tests single-service library injection in a Kubernetes environment

The scenario matrix and supported weblogs are defined in the configuration file `utils/scripts/ci_orchestrators/k8s_injector_dev.json`.

<!-- Content will be added here in the future -->