# Testing K8s library injection feature

1. [Run the tests](#run-the-tests)
   * [Run K8s library injection tests using the Wizard (Recommended)](#run-k8s-library-injection-tests-using-the-wizard-recommended)
   * [Run K8s library injection tests manually](#run-k8s-library-injection-tests-manually)
     - [Prerequisites](#prerequisites)
     - [Configure Private ECR Registry](#configure-private-ecr-registry)
     - [Configure tested components versions](#configure-tested-components-versions)
     - [Execute a test scenario](#execute-a-test-scenario)
2. [How to use a MiniKube implementation](#how-to-use-a-minikube-implementation)
3. [How to develop a test case](#how-to-develop-a-test-case)
   * [Folders and Files structure](#folders-and-files-structure)
   * [Implement a new test case](#implement-a-new-test-case)
4. [How to debug your kubernetes environment and tests results](#how-to-debug-your-kubernetes-environment-and-tests-results)
5. [How to debug your kubernetes environment at runtime](#how-to-debug-your-kubernetes-environment-at-runtime)
6. [Appendix: Public Registry Images (Reference)](#appendix-public-registry-images-reference)

## Run the tests

### Run K8s library injection tests using the Wizard (Recommended)

The easiest way to run K8s library injection tests is using the wizard script. The wizard will guide you through all the configuration steps interactively.

```sh
./utils/scripts/ssi_wizards/k8s_ssi_wizard.sh
```

The wizard will:

1. Check and install system-tests requirements
2. Let you choose a Kubernetes provider (Kind or Minikube)
3. Configure the private ECR registry authentication
4. Select the test language (Java, Node.js, Python, .NET, Ruby, PHP)
5. Select the scenario and weblog to test
6. Configure the weblog image (optionally build and push a custom one)
7. Select the cluster agent, lib-init, and injector images
8. Execute the tests

### Run K8s library injection tests manually

If you prefer to run the tests manually, follow the sections below.

#### Prerequisites

- Docker environment
- Kubernetes environment (Kind or Minikube)
- AWS CLI and aws-vault (for ECR access)

##### Docker environment

You should install Docker Desktop on your laptop.

##### Kubernetes environment

You should install Kind (or Minikube) and Helm Chart tool.
Kind is a tool for running local Kubernetes clusters using Docker container.
Helm uses a packaging format called charts. A chart is a collection of files that describe a related set of Kubernetes resources.

In order to install the Kind kubernetes tool you should execute this script:

```sh
KIND_VERSION='v0.17.0'
KUBECTL_VERSION='v1.25.3'

# Download appropriate version (Mac M1 arm64 arch or linux amd64)
echo "[build] Download installable artifacts"
ARCH=$(uname -m | sed 's/x86_//;s/i[3-6]86/32/')
if [ "$ARCH" = "arm64" ]; then
    curl -Lo ./kind https://github.com/kubernetes-sigs/kind/releases/download/$KIND_VERSION/kind-darwin-arm64
    KUBECTL_DOWNLOAD="darwin/arm64/kubectl"
else
    curl -Lo ./kind https://kind.sigs.k8s.io/dl/$KIND_VERSION/kind-linux-amd64
    KUBECTL_DOWNLOAD="linux/amd64/kubectl"
fi
curl -LO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/${KUBECTL_DOWNLOAD}"

echo "[build] Installing kind"
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
echo "[build] kind install complete"

echo "[build] Installing kubectl..."
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
echo "[build] kubectl install complete"
```

You also need the Helm Chart utility:

```sh
echo "[build] Installing helm"
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh
```

#### Configure Private ECR Registry

The K8s library injection tests use images stored in a private AWS ECR registry. You need to authenticate with the registry before running the tests.

##### Authentication with aws-vault

```sh
# Set the private registry environment variables
export PRIVATE_DOCKER_REGISTRY="235494822917.dkr.ecr.us-east-1.amazonaws.com"
export PRIVATE_DOCKER_REGISTRY_USER="AWS"

# Login to ECR
aws-vault exec sso-apm-ecosystems-reliability-account-admin -- aws ecr get-login-password | \
    docker login --username AWS --password-stdin 235494822917.dkr.ecr.us-east-1.amazonaws.com

# Set the registry token for the tests
export PRIVATE_DOCKER_REGISTRY_TOKEN=$(aws-vault exec sso-apm-ecosystems-reliability-account-admin -- aws ecr get-login-password --region us-east-1)
```

#### Configure tested components versions

All the software components to be tested can be configured using environment variables and command line parameters. Here's an example configuration for Java:

```sh
export TEST_LIBRARY=java
export WEBLOG_VARIANT=dd-lib-java-init-test-app
export LIBRARY_INJECTION_TEST_APP_IMAGE=235494822917.dkr.ecr.us-east-1.amazonaws.com/system-tests/dd-lib-java-init-test-app:latest
export LIB_INIT_IMAGE=235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-java-init:latest
export CLUSTER_AGENT_IMAGE=235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/cluster-agent:latest
export INJECTOR_IMAGE=235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/apm-inject:latest
```

##### Weblog image

The weblog images are stored in the private ECR registry with the following pattern:

```
235494822917.dkr.ecr.us-east-1.amazonaws.com/system-tests/<weblog-name>:latest
```

Available weblogs per language:

| LANG    | WEBLOG NAME                                      |
| ------- | ------------------------------------------------ |
| Java    | dd-lib-java-init-test-app                        |
| Java    | dd-djm-spark-test-app                            |
| .NET    | dd-lib-dotnet-init-test-app                      |
| Node.js | sample-app                                       |
| Python  | dd-lib-python-init-test-django                   |
| Python  | dd-lib-python-init-test-django-gunicorn          |
| Python  | dd-lib-python-init-test-django-gunicorn-alpine   |
| Python  | dd-lib-python-init-test-django-unsupported-package-force |
| Python  | dd-lib-python-init-test-django-uvicorn           |
| Ruby    | dd-lib-ruby-init-test-rails                      |
| Ruby    | dd-lib-ruby-init-test-rails-explicit             |
| Ruby    | dd-lib-ruby-init-test-rails-gemsrb               |
| PHP     | dd-lib-php-init-test-app                         |

###### Building a custom weblog image

If you want to build and push your own custom version of the weblog:

```sh
./lib-injection/build/build_lib_injection_weblog.sh -w $WEBLOG_VARIANT -l $TEST_LIBRARY \
    --push-tag $PRIVATE_DOCKER_REGISTRY/system-tests/$WEBLOG_VARIANT:my_custom_tag \
    --docker-platform linux/arm64,linux/amd64
```

##### Library init image

The library init images are stored in the private ECR registry. Available tags:

* **latest:** The latest release of the image.
* **latest_snapshot:** The image created when we build the main branch of the tracer library.

| LANG    | LIB INIT IMAGE (ECR)                                                        |
| ------- | --------------------------------------------------------------------------- |
| Java    | 235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-java-init:latest    |
| .NET    | 235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-dotnet-init:latest  |
| Node.js | 235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-js-init:latest      |
| Python  | 235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-python-init:latest  |
| Ruby    | 235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-ruby-init:latest    |
| PHP     | 235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-php-init:latest     |

##### Datadog Cluster Agent

The Datadog Cluster Agent images are stored in the private ECR registry:

| VERSION       | CLUSTER AGENT IMAGE (ECR)                                              |
| ------------- | ---------------------------------------------------------------------- |
| latest        | 235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/cluster-agent:latest  |
| 7.56.2        | 235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/cluster-agent:7.56.2  |

##### Injector image

The APM injector images are stored in the private ECR registry:

| TAG             | INJECTOR IMAGE (ECR)                                                    |
| --------------- | ----------------------------------------------------------------------- |
| latest          | 235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/apm-inject:latest      |
| latest_snapshot | 235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/apm-inject:latest_snapshot |

#### Execute a test scenario

Available scenarios:

- **K8S_LIB_INJECTION:** Minimal test scenario that runs a Kubernetes cluster and tests that the application is being instrumented automatically.
- **K8S_LIB_INJECTION_UDS:** Similar to previous scenario, but the communication between the agent and libraries is configured to use UDS.
- **K8S_LIB_INJECTION_NO_AC:** Configures the auto-injection adding annotations to the weblog pod, without using the admission controller.
- **K8S_LIB_INJECTION_NO_AC_UDS:** Similar to previous scenario, but the communication between the agent and libraries is configured to use UDS.
- **K8S_LIB_INJECTION_PROFILING_DISABLED:** Scenario that validates the profiling is not performing if it's not activated.
- **K8S_LIB_INJECTION_PROFILING_ENABLED:** Test profiling feature activation inside of Kubernetes cluster.
- **K8S_LIB_INJECTION_PROFILING_OVERRIDE:** Test profiling feature activation overriding the cluster configuration.
- **K8S_LIB_INJECTION_SPARK_DJM:** Allow us to verify the k8s injection works for Data Jobs Monitoring as new Java tracer, new auto_inject, and new cluster_agent are being released.
- **K8S_LIB_INJECTION_OPERATOR:** Tests using the Datadog Operator for library injection.

Run the minimal test scenario:

```sh
./run.sh K8S_LIB_INJECTION \
    --k8s-library $TEST_LIBRARY \
    --k8s-weblog $WEBLOG_VARIANT \
    --k8s-weblog-img $LIBRARY_INJECTION_TEST_APP_IMAGE \
    --k8s-lib-init-img $LIB_INIT_IMAGE \
    --k8s-cluster-img $CLUSTER_AGENT_IMAGE \
    --k8s-injector-img $INJECTOR_IMAGE \
    --k8s-provider kind
```

The allowed parameters are:

* **k8s-library:** Library to be tested.
* **k8s-weblog:** The sample application name.
* **k8s-weblog-img:** The image of the sample application.
* **k8s-lib-init-img:** Library init image to be tested.
* **k8s-cluster-img:** Datadog cluster agent image to be tested.
* **k8s-injector-img:** APM injector image to be tested.
* **k8s-provider:** K8s cluster provider. This parameter is optional. By default uses the Kind k8s cluster.

##### DJM Scenario

The following image illustrates the DJM scenario:

![DJM Scenario](../lib-injection/k8s_djm.png "DJM Scenario")

## How to use a MiniKube implementation

The K8s lib injection tests use the Kind cluster by default, but you can change this behaviour in order to use a MiniKube implementation. To do that you only need:

* Install Minikube locally: [Install MiniKube](https://minikube.sigs.k8s.io/docs/start/?arch=%2Fmacos%2Farm64%2Fstable%2Fbinary+download)
* Run the scenario adding the parameter `--k8s-provider minikube`

```sh
./run.sh K8S_LIB_INJECTION \
    --k8s-library nodejs \
    --k8s-weblog sample-app \
    --k8s-weblog-img 235494822917.dkr.ecr.us-east-1.amazonaws.com/system-tests/sample-app:latest \
    --k8s-lib-init-img 235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-js-init:latest \
    --k8s-cluster-img 235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/cluster-agent:latest \
    --k8s-injector-img 235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/apm-inject:latest \
    --k8s-provider minikube
```

## How to develop a test case

To develop a new test case in the K8s Library injection tests, you need to know about the project folder structure.

### Folders and Files structure

The following picture shows the main directories for the k8s lib injection tests:

![Folder structure](../lib-injection/k8s_lib_injections_folders.png "Folder structure")

The folders and files shown in the figure above are as follows:

* **lib-injection/build/docker:** This folder contains the sample applications with the source code and scripts that allow us to build and push docker weblog images.
* **tests/k8s_lib_injection:** All tests cases are stored on this folder. Conftests.py file manages the kubernetes cluster lifecycle.
* **utils/_context/scenarios:** In this folder you can find the K8s Lib injection scenario definition.
* **utils/k8s_lib_injection:** Here we can find the main utilities for the control and deployment of the components to be tested. For example:
  * **k8s_cluster_provider.py:** Implementation of the k8s cluster management. By default the provider is Kind, but you can use the MiniKube implementation or AWS EKS remote implementation.
  * **k8s_datadog_kubernetes.py:** Utils for:
    - Deploy Datadog Cluster Agent
    - Deploy Datadog Admission Controller
    - Extract Datadog Components debug information.
  * **k8s_weblog.py:**  Manages the weblog application lifecycle.
    - Deploy weblog as pod configured to perform library injection manually/without the Datadog admission controller.
    - Deploy weblog as pod configured to automatically perform the library injection using the Datadog admission controller.
    - Extract weblog debug information.
  * **k8s_command_utils.py:** Command line utils to launch the Helm Chart commands and other shell commands.

### Implement a new test case

All test cases associated to a scenario, will run on an isolated Kubernetes environment. The Kubernetes cluster will start up when the scenario is started (for local managed k8s providers).

All test cases can access to the K8s cluster information, using the "k8s_cluster_info" object stored in the scenario context. You can use this object to know about the open ports in the cluster (test agent port and weblog port) or to access to the Kubernetes Python API to interact with the cluster.

An example of a Kubernetes test:

```python
from tests.k8s_lib_injection.utils import get_dev_agent_traces, get_cluster_info

@features.k8s_admission_controller
@scenarios.k8s_lib_injection
class TestExample:
    def test_example(self):
        logger.info(
            f"Test config: Weblog - [{get_cluster_info().get_weblog_port()}] Agent - [{get_cluster_info().get_agent_port()}]"
        )
        # This test will be executed after the k8s starts and after deploy all the tested components on the cluster

        # Check that app was auto instrumented
        traces_json = get_dev_agent_traces(get_cluster_info())
        assert len(traces_json) > 0, "No traces found"
```

## How to debug your kubernetes environment and tests results

In the testing kubernetes scenarios, multiple components are involved and sometimes can be painful to debug a failure.
You can find a folder named "logs_[scenario name]" with all the logs associated with the execution.
In the following image you can see the log folder content:

![Log folder structure](../lib-injection/k8s_lib_injections_log_folders.png "Log folder structure")

These are the main important log/data files:

* **test.log:** General log generated by system-tests.
* **report.json:** Pytest results report.
* **feature_parity.json:** Report to push the results to Feature Parity Dashboard.
* **lib-injection-testing-xyz-config.yaml:** The kind cluster configuration. In this file you can check the open ports for each cluster and test case.
* **lib-injection-testing-xyz_help_values:** Helm chart operator values for each test case.
* **daemon.set.describe.log:** Datadog Cluster daemon set logs.
* **datadog-XYZ_events.log:** Kubernetes events for Datadog Agent.
* **datadog-cluster-agent-XYZ_status.log:** Datadog Cluster Agent current status.
* **datadog-cluster-agent-XYZ_telemetry.log:** Telemetry for Datadog Cluster Agent.
* **datadog-cluster-agent.log:** Logs generated by Datadog Cluster Agent.
* **datadog-cluster-agent-XYZ_event.log:** Kubernetes events for Datadog Cluster Agent.
* **deployment.describe.log:** Describe all deployment in the Kubernetes cluster.
* **deployment.logs.log:** All deployments logs.
* **get.deployments.log:** Deployments list.
* **get.pods.log:** Current started pod list.
* **myapp.describe.log:** Describe weblog pod.
* **myapp.logs.log:** Current weblog pod logs. It could be empty if we are deploying the weblog as Kubernetes deployment.
* **test-LANG-deployment-XYZ_events.log:** Current weblog deployment events. Here you can see the events generated by auto instrumentation process. It could be empty if we are deploying the weblog application as Pod.

## How to debug your kubernetes environment at runtime

You can use the `--sleep` parameter in the run command line of the scenario to keep the K8s cluster alive with all the tested components deployed.

[Check the sleep parameter documentation](https://github.com/DataDog/system-tests/blob/main/docs/execute/run.md#spawn-components-but-do-nothing)

## Appendix: Public Registry Images (Reference)

For reference, the following public registry images are also available. These can be used as alternatives or for migrating to a custom private registry.

### Public Library Init Images

| LANG    | LIB INIT IMAGE (Public)                                            |
| ------- | ------------------------------------------------------------------ |
| Java    | gcr.io/datadoghq/dd-lib-java-init:latest                           |
| Java    | ghcr.io/datadog/dd-trace-java/dd-lib-java-init:latest_snapshot     |
| .NET    | gcr.io/datadoghq/dd-lib-dotnet-init:latest                         |
| .NET    | ghcr.io/datadog/dd-trace-dotnet/dd-lib-dotnet-init:latest_snapshot |
| Node.js | gcr.io/datadoghq/dd-lib-js-init:latest                             |
| Node.js | ghcr.io/datadog/dd-trace-js/dd-lib-js-init:latest_snapshot         |
| Python  | gcr.io/datadoghq/dd-lib-python-init:latest                         |
| Python  | ghcr.io/datadog/dd-trace-py/dd-lib-python-init:latest_snapshot     |
| Ruby    | gcr.io/datadoghq/dd-lib-ruby-init:latest                           |
| Ruby    | ghcr.io/datadog/dd-trace-rb/dd-lib-ruby-init:latest_snapshot       |

### Public Cluster Agent and Injector Images

| COMPONENT      | IMAGE (Public)                          |
| -------------- | --------------------------------------- |
| Cluster Agent  | gcr.io/datadoghq/cluster-agent:latest   |
| APM Injector   | gcr.io/datadoghq/apm-inject:latest      |

### Migrating Public Images to Private Registry

If you need to use a custom private registry, you can migrate the public images:

```sh
# Example: Migrate lib-init image
docker pull gcr.io/datadoghq/dd-lib-java-init:latest
docker tag gcr.io/datadoghq/dd-lib-java-init:latest $PRIVATE_DOCKER_REGISTRY/ssi/dd-lib-java-init:latest
docker push $PRIVATE_DOCKER_REGISTRY/ssi/dd-lib-java-init:latest

# Example: Migrate cluster-agent
docker pull gcr.io/datadoghq/cluster-agent:latest
docker tag gcr.io/datadoghq/cluster-agent:latest $PRIVATE_DOCKER_REGISTRY/ssi/cluster-agent:latest
docker push $PRIVATE_DOCKER_REGISTRY/ssi/cluster-agent:latest

# Example: Migrate apm-inject
docker pull gcr.io/datadoghq/apm-inject:latest
docker tag gcr.io/datadoghq/apm-inject:latest $PRIVATE_DOCKER_REGISTRY/ssi/apm-inject:latest
docker push $PRIVATE_DOCKER_REGISTRY/ssi/apm-inject:latest
```

The wizard script also offers an option to automatically migrate public images to your private registry.
