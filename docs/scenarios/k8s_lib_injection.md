# Testing K8s library injection feature

1. [Overall](#Overall)
    * [What is the library injection feature?](#What-is-the-k8s-library-injection-feature?)
    * [What’s the Datadog Cluster Agent and why?](#What’s-the-Datadog-Cluster-Agent-and-why?)
2. [K8s tested components](#K8s-tested-components)
3. [Run the tests](#K8s-tested-components)
    * [Run K8s library image validation](#Run-K8s-library-image-validation)
    * [Run K8s library injection tests](#Run-K8s-library-injection-tests)
      - [Prerequisites](#Prerequisites)
      - [Configure tested components versions](#Configure-tested-components-versions)
      - [Execute a test scenario](#Execute-a-test-scenario)
4. [How to develop a test case](#How-to-develop-a-test-case)
    * [Folders and Files structure](#Folders-and-Files-structure)
    * [Implement a new test case](#Implement-a-new-test-case)
5. [How to debug your kubernetes environment and tests results](#How-to-debug-your-kubernetes-environment-and-tests-results)

## Overall

### What is the k8s library injection feature?

The lib-injection project is a feature to allow injection of the Datadog library
into a customer's application container without requiring them to modify their
application images.

This feature enables applications written in Java, Node, Python, DotNet or Ruby running
in Kubernetes to be automatically instrumented with the corresponding Datadog
APM libraries.

Currently, there are two different ways to have the Datadog library injected
into the application container:

1) **Manually via Kubernetes annotations**:
    * Using Datadog Admission Controller: [Injecting Libraries Kubernetes](https://docs.datadoghq.com/tracing/trace_collection/admission_controller/).
    * Adding library injection specific annotations (without Datadog Admission Controller): [Application Instrumentation](https://docs.datadoghq.com/tracing/trace_collection/), [Add the Datadog Tracing Library](https://docs.datadoghq.com/tracing/trace_collection/)
2) **Automatically with Remote Config via the Datadog UI.**


### What’s the Datadog Cluster Agent and why?

The Cluster Agent is a different binary (vs the regular Agent), written in Go in the same DataDog/datadog-agent repo and is installed as a Deployment in Kubernetes, not a DaemonSet. It’s an essential component for cluster-level monitoring.

In addition to the local API (Kubelet) leveraged by the Datadog Agent on each node, Kubernetes has a centralized and powerful API called API Server.
The Datadog Cluster Agent provides a streamlined, centralized approach to collecting cluster level monitoring data from the Kubernetes API Server. The Cluster Agent also leverages the Kubernetes API Server for advanced features like the Admission Controller.

Kubernetes admission controllers are plugins that govern and enforce how the cluster is used. They can intercept API requests and may change the request object or deny the request altogether. Read more in A Guide to Kubernetes Admission Controllers and Dynamic Admission Control

The Datadog admission controller is a component of the Datadog Cluster Agent. It leverages the Kubernetes mutatingwebhookconfigurations.admissionregistration.k8s.io API.

## K8s tested components

K8s Library injection testing is part of the "system-tests" test suite.

As a final purpose we want to check the correct operation of all Datadog components involved in the auto instrumentation of the applications deployed in a kubernetes cluster.

In the auto-instrumentation proccess there are several software components involved:

- **Cluster agent:** Software component, written in Go, that resides on the DataDog/datadog-agent repository and is installed as a Deployment in Kubernetes.
- **Injector image:** Directly involved in auto-instrumentation. Resides on Datadog/auto_inject repository.
- **Library image (lib-init):** Contains the tracer library to be injected in the pods.

These test components are also involved through the testing process:

- **System-tests runner:** The core of the system-tests is the reponsible for orchestrate the tests execution and manage the tests results.
- **Dev test agent:**  The APM Test Agent container help us to perform the validations ([APM Test Agent](https://github.com/DataDog/dd-apm-test-agent)).
- **Sample app/weblog:** Containerized sample application implemented on Java, Nodejs, dotNet, Ruby or Python.

The following image represents, in general terms, the necessary and dependent architecture to be able to run the K8s library injection tests:

![Architecture overview](../lib-injection/lib-injection-tests.png "Architecture overview")

## Run the tests

### Run K8s library image validation

We have created some simple tests, able to auto inject the tracer library in any application running in a docker container.
On the test application container (weblog), the lib-init image will be added as a docker volume and the environment variables, necessary for auto injection, will be attached.
The weblog application only requires to be listening on port 18080.
The weblog will be deployed together with the APM Test Agent container, which will help us to perform the validations ([APM Test Agent](https://github.com/DataDog/dd-apm-test-agent)).

Now we can test the auto instrumentation on any image in two simple steps:

1. **Build your app image and tag locally as "weblog-injection:latest"** :

``` docker build  -t weblog-injection:latest .```

  You could use the existing weblog apps under __lib-injection/build/docker__ folder. Use the existing script to build them:

``` lib-injection/build/build_lib_injection_weblog.sh -w [existing weblog] -l [java,nodejs,dotnet,ruby,python]  ```

ie:
```
lib-injection/build/build_lib_injection_weblog.sh -w dd-lib-dotnet-init-test-app -l dotnet
```

2. **Run the scenario that checks if weblog app is auto instrumented and sending traces to the _Dev Test Agent_**:
```
TEST_LIBRARY=dotnet
LIB_INIT_IMAGE=ghcr.io/datadog/dd-trace-dotnet/dd-lib-dotnet-init:latest_snapshot
./run.sh LIB_INJECTION_VALIDATION
```

#### Validating lib-injection images under not supported language runtime version

You can also validate weblog applications implemented with a language version that is not supported by the tracer. The scenario will check that the app is running although the app is not instrumented:
```
lib-injection/build/build_lib_injection_weblog.sh -w jdk7-app -l java
TEST_LIBRARY=java
LIB_INIT_IMAGE=ghcr.io/datadog/dd-trace-java/dd-lib-java-init:latest_snapshot
./run.sh LIB_INJECTION_VALIDATION_UNSUPPORTED_LANG
```
### Run K8s library injection tests

These tests can run locally easily. You only have to install the environment and configure it as follow sections detail.

#### Prerequisites:
- Docker environment
- Kubernetes environment

##### Docker enviroment

You should install the docker desktop on your laptop.
You need to access to GHCR.
Usually you only need to access to GHCR to pull the images, but you can also push your custom images to your Docker Hub account. To do that you need login to Docker Hub account:

```cat ~/my_password.txt | docker login --username my_personal_user --password-stdin ```

##### Kubernetes environment

You should install the kind and Helm Chart tool.
Kind is a tool for running local Kubernetes clusters using Docker container.
Helm uses a packaging format called charts. A chart is a collection of files that describe a related set of Kubernetes resources.

In order to install the kind kubernetes tool you should execute this script:

```
KIND_VERSION='v0.17.0'
KUBECTL_VERSION='v1.25.3'

# Download appropriate version (Mac M1 arm64 arch or linux amd64)
echo "[build] Download installable artifacts"
ARCH=$(uname -m | sed 's/x86_//;s/i[3-6]86/32/')
if [ "$ARCH" = "arm64" ]; then
    curl -Lo ./kind https://github.com/kubernetes-sigs/kind/releases/download/$KIND_VERSION/kind-darwin-amd64
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

```
echo "[build] Installing helm"
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh
```

#### Configure tested components versions

All the software components to be tested are configured using environment variables. This is an example of env vars configuration for Java:

```sh
export TEST_LIBRARY=java
export WEBLOG_VARIANT=dd-lib-java-init-test-app #Which variant do we want to use?
export LIBRARY_INJECTION_TEST_APP_IMAGE=ghcr.io/datadog/system-tests/dd-lib-java-init-test-app:latest #weblog variant in the registry
export LIB_INIT_IMAGE=gcr.io/datadoghq/dd-lib-java-init:latest # What is the lib init image that we want to test?
export CLUSTER_AGENT_VERSION=7.56.2
export INJECTOR_IMAGE=TODO
```
---
**NOTE: Injector image**

Currently the tests do not allow selection of the injector image. The image used will be the one pointed by the cluster agent by default.

---

##### Weblog image

The images of sample applications are automatically uploaded to the GHCR registry by the CI.

But in case you want to build your own custom version of the application, you can do the following (the weblog images must be allwasys on a docker registry):

```sh
  export LIBRARY_INJECTION_TEST_APP_IMAGE=ghcr.io/datadog/system-tests/dd-lib-java-init-test-app:my_custom_tag #weblog variant in the registry
  lib-injection/build/build_lib_injection_weblog.sh -w $WEBLOG_VARIANT -l $TEST_LIBRARY --push-tag $LIBRARY_INJECTION_TEST_APP_IMAGE
```

or if you don't have the permission to push the image to GHCR, you can use your docker hub account (after loging into it):

```sh
  export LIBRARY_INJECTION_TEST_APP_IMAGE=registry.hub.docker.com/<user>/dd-lib-java-init:my_custom_tag #weblog variant in the registry
  lib-injection/build/build_lib_injection_weblog.sh -w $WEBLOG_VARIANT -l $TEST_LIBRARY --push-tag $LIBRARY_INJECTION_TEST_APP_IMAGE
```

The sample applications currently available in GHCR are:

|  LANG | WEBLOG IMAGE |
|---|---|
| Java |  ghcr.io/datadog/system-tests/dd-lib-java-init-test-app:latest  |
| Java | ghcr.io/datadog/system-tests/dd-djm-spark-test-app:latest  |
| DotNet  | ghcr.io/datadog/system-tests/dd-lib-dotnet-init-test-app:latest  |
| Nodejs  | ghcr.io/datadog/system-tests/sample-app:latest  |
| Python  | ghcr.io/datadog/system-tests/dd-lib-python-init-test-django:latest  |
| Python  | ghcr.io/datadog/system-tests/dd-lib-python-init-test-django-gunicorn:latest  |
| Python  | ghcr.io/datadog/system-tests/dd-lib-python-init-test-django-gunicorn-alpine:latest  |
| Python  | ghcr.io/datadog/system-tests/dd-lib-python-init-test-django-preinstalled:latest  |
| Python  | ghcr.io/datadog/system-tests/dd-lib-python-init-test-django-unsupported-package-force:latest  |
| Python  | ghcr.io/datadog/system-tests/dd-lib-python-init-test-django-uvicorn:latest  |
| Python  | ghcr.io/datadog/system-tests/dd-lib-python-init-test-protobuf-old:latest  |
| Ruby  | ghcr.io/datadog/system-tests/dd-lib-ruby-init-test-rails:latest  |
| Ruby  | ghcr.io/datadog/system-tests/dd-lib-ruby-init-test-rails-explicit":latest  |
| Ruby  | ghcr.io/datadog/system-tests/dd-lib-ruby-init-test-rails-gemsrb:latest  |

##### Library init image

The library init images are created by each tracer library and these images will be pushed to the registry using two tags:
* **latest:** The latest release of the image.
* **latest_snapshot:** The image created when we build the main branch of the tracer library.

The list of available images is:

|  LANG | LIB INIT IMAGE |
|---|---|
| Java |  gcr.io/datadoghq/dd-lib-java-init:latest |
| Java | ghcr.io/datadog/dd-trace-java/dd-lib-java-init:latest_snapshot  |
| DotNet  | gcr.io/datadoghq/dd-lib-dotnet-init:latest |
| DotNet  | ghcr.io/datadog/dd-trace-dotnet/dd-lib-dotnet-init:latest_snapshot |
| Nodejs  | gcr.io/datadoghq/dd-lib-js-init:latest |
| Nodejs  | ghcr.io/datadog/dd-trace-js/dd-lib-js-init:latest_snapshot |
| Python  | gcr.io/datadoghq/dd-lib-python-init:latest |
| Python  | ghcr.io/datadog/dd-trace-py/dd-lib-python-init:latest_snapshot  |
| Ruby  | gcr.io/datadoghq/dd-lib-ruby-init:latest  |
| Ruby  | ghcr.io/datadog/dd-trace-rb/dd-lib-ruby-init:latest_snapshot |

##### Datadog Cluster Agent

The Datadog Cluster Agent versions available for tests are:
- 7.56.2
- 7.57.0
- 7.59.0

##### Injector image

TODO

#### Execute a test scenario

If we have followed the previous steps, we already have the environment configured and we only need to run any of the available scenarios:
- **K8S_LIBRARY_INJECTION_BASIC:** Minimal test scenario that run a Kubernetes cluster and test that the application is being instrumented automatically.
- **K8S_LIBRARY_INJECTION_PROFILING:** Test profiling feature inside of Kubernetes cluster.
- **K8S_LIBRARY_INJECTION_DJM:** Allow us to verify the k8s injection continue to work for Data Jobs Monitoring as new Java tracer, new auto_inject, and new cluster_agent are being released.

Run the minimal test scenario:

```sh
  ./run.sh K8S_LIBRARY_INJECTION_BASIC
```

##### DJM Scenario

The following image ilustrates the DJM scenario:

![DJM Scenario](../lib-injection/k8s_djm.png "DJM Scenario")

## How to develop a test case

To develop a new test case in the K8s Library injection tests, you need to know:

- The project folder structure.
- The parameters that you will recive in your test case (Parametrized test)

### Folders and Files structure

The following picture shows the main directories for the k8s lib injection tests:

![Folder structure](../lib-injection/k8s_lib_injections_folders.png "Folder structure")

The folders and files shown in the figure above are as follows:

* **lib-injection/build/docker:** This folder contains the sample applications with the source code and scripts that allow us to build and push docker weblog images.
* **tests/k8s_lib_injection:** All tests cases are stored on this folder. Conftests.py file manages the kubernetes cluster lifecycle.
* **utils/_context/scenarios:**: In this folder you can find the K8s Lib injection scenario definition.
* **utils/k8s_lib_injection:** Here we can find the main utilities for the control and deployment of the components to be tested. For example:
  * **k8s_kind_cluster.py:** Tools for creating and destroying the Kubernetes cluster.
  * **k8s_datadog_kubernetes.py:** Utils for:
    - Deploy Datadog Cluster Agent
    - Deploy Datadog Admission Controller
    - Apply Kubernetes ConfigMap
    - Extract Datadog Components debug information.
  * **k8s_weblog.py:**  Manages the weblog application lifecycle.
    - Deploy weblog as pod configured to perform library injection manually/without the Datadog admission controller.
    - Deploy weblog as pod configured to automatically perform the library injection using the Datadog admission controler.
    - Deploy weblog as Kubernetes deployment and prepare the library injection using Kubernetes ConfigMaps and Datadog Admission Controller.
    - Extract weblog debug information.
  * **k8s_command_utils.py:** Command line utils to lauch the Helm Chart commands and others shell commands.

### Implement a new test case

All test cases for K8s will run on an isolated Kubernetes environment. For each test case we are going to start up a Kubernetes Cluster. In this way we can run the tests in parallel.
Each test case will receive a "test_k8s_instance" object with these main properties loaded:
* **library:** Current testing library (java, python...)
* **weblog_variant:** Current sample application name (weblog name)
* **weblog_variant_image:** Reference to the weblog image in the registry
* **library_init_image:** Reference to the library init image in the registry
* **output_folder:** Path to log folder for the current test.
* **test_name:** Name of the current test.
* **test_agent:** Instance of the object that contains the main methods to access to Datadog Cluster Agent (Deploy agent, deploy operator, apply configmaps...). See utils/k8s_lib_injection/k8s_datadog_cluster_agent.py.
* **test_weblog:** Instance of the object that contains the main methods to access to weblog variant funtionalities (Deploy pod, deployments...). See utils/k8s_lib_injection/k8s_weblog.py.
* **k8s_kind_cluster:** Contains the information of the Kubernetes cluster associated to the test.
  - cluster_name: Random name associated to the cluster.
  - context_name: Kind cluster name
  - agent_port: Agent port
  - weblog_port: Weblog port

The "test_k8s_instance" also contains some basic methods, that you can use directly instead of working with either "k8s_datadog_cluster_agent" or "k8s_weblog":
* start_instance
* destroy_instance
* deploy_test_agent
* deploy_weblog_as_pod
* deploy_weblog_as_deployment
* export_debug_info

Feel free to use the methods listed above or use the methods encapsulated in both "k8s_datadog_cluster_agent" and "k8s_weblog" or directly use the Kubernates Python Client to manipulate the Kunernates cluster components.

An example of a Kubernetes test:

```python

from tests.k8s_lib_injection.utils import get_dev_agent_traces

@features.k8s_admission_controller
@scenarios.k8s_library_injection_basic
class TestExample:
    def test_example(self, test_k8s_instance):
        logger.info(
            f"Test config: Weblog - [{test_k8s_instance.k8s_kind_cluster.get_weblog_port()}] Agent - [{test_k8s_instance.k8s_kind_cluster.get_agent_port()}]"
        )
        #Deploy test agent
        test_k8s_instance.deploy_test_agent()
        #Deploy cluster agent with admission controller
        test_k8s_instance.deploy_datadog_cluster_agent()
        #Deploy weblog
        test_k8s_instance.deploy_weblog_as_pod()
        #Check that app was auto instrumented
        traces_json = get_dev_agent_traces(test_k8s_instance.k8s_kind_cluster)
        assert len(traces_json) > 0, "No traces found"
```
You can also add environment variables to your pod, for example:

```python
    test_k8s_instance.deploy_weblog_as_pod(
      env={"DD_PROFILING_UPLOAD_PERIOD": "10", "DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD": "1500"}
    )
```

Or you can activate DD features from the Cluster agent:

```python
    test_k8s_instance.deploy_datadog_cluster_agent(features={"datadog.profiling.enabled": "auto"})
```

## How to debug your kubernetes environment and tests results

In the testing kubernetes scenarios, multiple components are involved and sometimes can be painfull to debug a failure. Even more so when running all tests in parallel.
You can find a folder named "logs_[scenario name]" with a separe folder per test case.
In the following image you can see the log folder content:

![Log folder structure](../lib-injection/k8s_lib_injections_log_folders.png "Log folder structure")

These are the main important log/data files:

* **test.log:** General log generated by system-tests.
* **report.json:** Pytest results report.
* **feature_parity.json:** Report to push the results to Feature Parity Dashboard.
* **lib-injection-testing-xyz-config.yaml:** The kind cluster configuration. In this file you can check the open ports for each cluster and test case.
* **lib-injection-testing-xyz_help_values:** Helm chart operator values for each test case.
* **<testcase_folder>/applied_configmaps.log:** ConfigMaps applied in the testcase (it could be empty if there are no configmaps applied).
* **<testcase_folder>/daemon.set.describe.log:** Datadog Cluster daemon set logs.
* **<testcase_folder>/datadog-XYZ_events.log:** Kubernetes events for Datadog Agent.
* **<testcase_folder>/datadog-cluster-agent-XYZ_status.log:** Datadog Cluster Agent current status.
* **<testcase_folder>/datadog-cluster-agent-XYZ_telemetry.log:** Telemetry for Datadog Cluster Agent.
* **<testcase_folder>/datadog-cluster-agent.log:** Logs generated by Datadog Cluster Agent.
* **<testcase_folder>/datadog-cluster-agent-XYZ_event.log:** Kubernetes events for Datadog Cluster Agent.
* **<testcase_folder>/deployment.describe.log:** Describe all deployment in the Kubernetes cluster.
* **<testcase_folder>/deployment.logs.log:** All deployments logs.
* **<testcase_folder>/events_configmaps.log:** Events generated when we apply a configmap.
* **<testcase_folder>/get.deployments.log:** Deployments list.
* **<testcase_folder>/get.pods.log:** Current started pod list.
* **<testcase_folder>/k8s_logger.log:** Specific logs for current test case.
* **<testcase_folder>/myapp.describe.log:** Describe weblog pod.
* **<testcase_folder>/myapp.logs.log:** Current weblog pod logs. It could be empty if we are deploying the weblog as Kubernetes deployment.
* **<testcase_folder>/test-LANG-deployment-XYZ_events.log:** Current weblog deployment events. Here you can see the events generated by auto instrumention process. It could be empty if we are deploying the weblog application as Pod.
