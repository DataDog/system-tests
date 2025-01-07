1. [Overall](#Overall)
2. [Run the tests](#Run-the-tests)
   * [Prerequisites](#Prerequisites)
     - [System-tests requirements](#System-tests-requirements)
   * [Run the scenario](#run-the-scenario)
3. [How to develop tests](#How-to-develop-a-test-case)
   * [Folders and Files structure](#Folders-and-Files-structure)
   * [Create a new provision](#Create-a-new-provision)
   * [Create a new weblog](#Create-a-new-weblog)
   * [Create a new test case](#Create-a-new-test-case)
4. [How to debug your environment and tests results](#How-to-debug-your-environment-and-tests-results)
5. [How to debug a virtual machine at runtime](#How-to-debug-a-virtual-machine-at-runtime)

# Overall

The Docker SSI tests are an easy and fast tests to check the SSI instrumentation.
The Docker SSI tests don't pretend to reemplace the current AWS tests, there only try to complement them, providing a quick checks and verification for some features included in the SSI.

The main differences between the AWS/Onboarding tests and the Docker SSI tests are:

* In Docker SSI, the SSI is installed inside a docker container, instead of using virtual machines.
* The AWS/Onboarding tests represent better a real customer scenarios, but Docker SSI it doesn't.
* Docker SSI relies on APM Test Agent, instead of rely on the backend.

The main Docker SSI properties are:

* Install the SSI host injection on the docker container that runs the weblog application.
* Uses a APM Test Agent to make the assertions.
* The weblog applications are containerized applications.
* The weblog application container is built by the system-tests scenarios in separate steps.
* The base image of the weblog application container should be parametrizable (it will detailed in the next sections)

The Docker SSI are good for:

* Test the instrumentation agains different runtime versions.
* Test the guardrail features (unsupported versions of the language).
* Test the service naming features on SSI.
* Test the crash tracking features.
* Test other features like profiling, asm...

# Run the tests

## Prerequisites

There are not special requirements to run the Docker SSI tests, you only need the docker engine and have the access to GHCR.

### System-tests requirements

All system-tests assertions and utilities are based on python and pytests. You need to prepare this environment before run the tests:

- Python and pytests environment as described: [configure python and pytests for system-tests](../../README.md#requirements).
- Ensure that requirements.txt is loaded (you can run "`./build.sh -i runner`")

## Run the scenario

There is only one scenario declared: "`DOCKER_SSI`". But this unique scenario can run agains multiple variants of weblogs, conteinerized OS and architectures and therefore the matrix combinations might be very big.

To help us to run a concrete case of the matrix variants, there are two scripts to be executed locally:

* `utils/build/ssi/build_local_manual.sh`: Runs the Docker SSI scenario using the arguments: library, weblog, docker base image, architecture and installable runtime. To run this command you need to know the correct combination of these arguments.
* `utils/build/ssi/build_local_wizard.sh`: Interactive shell wizard that allow you to execute the Docker SSI scenario with the correct combination of arguments.

Here is the command line and the mandatory parameters:

```bash
  ./run.sh DOCKER_SSI --ssi-weblog "$weblog" --ssi-library "$TEST_LIBRARY" --ssi-base-image "$base_image" --ssi-arch "$arch" --ssi-installable-runtime "$installable_runtime"

```

The easy way to execute this scenario is to use the wizard script. For example:

```bash
(venv) system-tests % utils/build/ssi/build_local_wizard.sh
Welcome to the SSI Wizard!
Please select the library you want to test:
1) dotnet
2) java
3) nodejs
4) php
5) python
#? 2
You selected: java
Please select the weblog you want to use:
1) java7-app      3) jetty-app      5) websphere-app
2) jboss-app      4) tomcat-app
#? 3
You selected: jetty-app
Please select the base image you want to use:
1) almalinux:8.10    3) oraclelinux:8.10  5) ubuntu:16.04
2) almalinux:9.4     4) oraclelinux:9     6) ubuntu:22.04
#? 6
You selected: ubuntu:22.04
Please select the architecture you want to use:
1) linux/amd64
2) linux/arm64
#? 2
You selected: linux/arm64
Please select the installable runtime you want to use:
1) 11.0.24-zulu
2) 17.0.12-zulu
3) 21.0.4-zulu
4) 22.0.2-zulu
#? 3
You selected: 21.0.4-zulu
Enter any extra arguments (or leave blank):
Executing: ./run.sh DOCKER_SSI --ssi-weblog jetty-app --ssi-library java --ssi-base-image ubuntu:22.04 --ssi-arch linux/arm64 --ssi-installable-runtime 21.0.4-zulu
```

# How to develop tests

## Folders and Files structure

To develop a new test case in the Docker SSI Library injection tests, you need to know about the project folder structure.
The following picture shows the main directories for the Docker SSI tests:

![Folder structure](../lib-injection/docker_ssi_lib_injections_folders.png "Folder structure")

* **tests/docker_ssi:** All tests cases are stored on this folder.
* **utils/_context/scenarios/**: In this folder you can find the Docker SSI Lib injection scenario definition.
* **utils/build/ssi/base/:** The base templates for the Docker SSI images, and the base utilities used to build the images, for example the language runtime installers.
* **utils/build/ssi/[lang]/:** The weblog applications docker definitios.
* **utils/build/ssi/build_local_manual.sh:** The helper script to run the Docker SSI scenarios.
* **utils/build/ssi/build_local_wizard.sh:** The wizard script to run the Docker SSI scenarios.
* **utils/docker_ssi:** The core implementation of this test framework.

## Docker SSI definitions

The key of the matrix of OSs (docker base image), architectures, language versions and weblogs resides on the file: `utils/docker_ssi/docker_ssi_definitions.py`. This file is the glue for all the components of this large matrix.

The first component is the Supported Images definition:

```python
class SupportedImages:
    """All supported images"""

    def __init__(self) -> None:
        # Try to set the same name as utils/_context/virtual_machines.py
        self.UBUNTU_22_AMD64 = DockerImage("Ubuntu_22", "ubuntu:22.04", LINUX_AMD64)
        self.UBUNTU_22_ARM64 = DockerImage("Ubuntu_22", "ubuntu:22.04", LINUX_ARM64)
        self.UBUNTU_16_AMD64 = DockerImage("Ubuntu_16", "ubuntu:16.04", LINUX_AMD64)
        self.UBUNTU_16_ARM64 = DockerImage("Ubuntu_16", "ubuntu:16.04", LINUX_ARM64)
        self.CENTOS_7_AMD64 = DockerImage("CentOS_7", "centos:7", LINUX_AMD64)
```

Other component to be defined is the installable runtime versions of the languages that are supported:

```python
class JavaRuntimeInstallableVersions:
    """Java runtime versions that can be installed automatically"""

    JAVA_22 = RuntimeInstallableVersion("JAVA_22", "22.0.2-zulu")
    JAVA_21 = RuntimeInstallableVersion("JAVA_21", "21.0.4-zulu")
    JAVA_17 = RuntimeInstallableVersion("JAVA_17", "17.0.12-zulu")
    JAVA_11 = RuntimeInstallableVersion("JAVA_11", "11.0.24-zulu")

class PHPRuntimeInstallableVersions:
    """PHP runtime versions that can be installed automatically"""

    PHP56 = RuntimeInstallableVersion("PHP56", "5.6")
    PHP70 = RuntimeInstallableVersion("PHP70", "7.0")
    PHP71 = RuntimeInstallableVersion("PHP71", "7.1")

```

Finally, there is a place to define the weblogs and specify on which OSs/docker base images can be deployed and whether it supports the installation of different language versions.

```python
JS_APP = WeblogDescriptor(
    "js-app",
    "nodejs",
    [
        SupportedImages().UBUNTU_22_AMD64.with_allowed_runtime_versions(
            JSRuntimeInstallableVersions.get_all_versions()
        ),
        SupportedImages().UBUNTU_22_ARM64.with_allowed_runtime_versions(
            JSRuntimeInstallableVersions.get_all_versions()
        ),
    ],
)
```

Might be your weblog only supports one base image and it's required a runtime version to be installed, for example:

```python
TOMCAT_APP = WeblogDescriptor("tomcat-app", "java", [SupportedImages().TOMCAT_9_ARM64])
JAVA7_APP = WeblogDescriptor("java7-app", "java", [SupportedImages().UBUNTU_22_ARM64])
WEBSPHERE_APP = WeblogDescriptor("websphere-app", "java", [SupportedImages().WEBSPHERE_AMD64])
JBOSS_APP = WeblogDescriptor("jboss-app", "java", [SupportedImages().JBOSS_AMD64])
```

## Create a new weblog

daff

## Create a new test case

dasfs

# How to debug your environment and tests results

In the virtual machine scenarios, multiple components are involved and sometimes can be painfull to debug a failure. You can find a folder named "logs_[scenario name]" with all the logs associated with the execution In the following image you can see the log folder content:

![Log folder structure](../lib-injection/ssi_lib_injections_log_folders.png "Log folder structure")

These are the main important log/data files:

* **test.log:** General log generated by system-tests. Here you will see the Pulumi outputs of the remote provisions.
* **report.json:** Pytest results report.
* **feature_parity.json:** Report to push the results to Feature Parity Dashboard.
* **report.json:** Pytest results report.
* **[vm name].log:** Logs related with the remote commands executed on the machine.
* **vms_desc.log:** Contains the IP assigned to the remote machine.
* **tested_components.log:** Contains a JSON with the versions of the components that are being tested in this scenario.
* **[machine name]/var/log/datadog/:** In this folder you will see the outputs of the datadog agent and all related deployed components.
* **[machine name]/var/log/datadog_weblog/app.log:** Logs produced by the weblog application.

# How to debug a virtual machine at runtime

Locally you can debug the remote machine by SSH. To do that you only need:

* Keep alive the machine after the test execution.
* Use your own AWS key-pair to configure the SSH connection and connect to the machine ([Create a key pair for your Amazon EC2 instance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/create-key-pairs.html)).

You can do that using the environment variables. For example:

```bash
#Mandatory env variables
export ONBOARDING_AWS_INFRA_SUBNET_ID=subnet-xyz
export ONBOARDING_AWS_INFRA_SECURITY_GROUPS_ID=sg-xyz
export DD_API_KEY_ONBOARDING=apikey
export DD_APP_KEY_ONBOARDING=appkey

#The key pair configuration
export ONBOARDING_AWS_INFRA_KEYPAIR_NAME="my_key_pair"
export ONBOARDING_AWS_INFRA_KEY_PATH="/home/my_user/key_pairs/my_key_pair.pem"

#Variables to keep alive the machine after run the tests
export ONBOARDING_KEEP_VMS="true"
export ONBOARDING_LOCAL_TEST="true"

#Run the tests
./run.sh SIMPLE_INSTALLER_AUTO_INJECTION --vm-weblog test-app-nodejs --vm-env dev --vm-library nodejs --vm-provider aws --vm-only Ubuntu_22_amd64

```

After the test execution, you will need to open the log file "logs_folder/vms_desc.log" to get the remote machine IP, after that, you should be able to access to the machine in a interactive shell:

```bash
ssh -i "/home/my_user/key_pairs/my_key_pair.pem" ec2-user@99.99.99.99
```

You can also use SCP to upload and download files to/from the remote machine:

```bash
scp -i "/home/my_user/key_pairs/my_key_pair.pem" ubuntu@99.99.99.99:/home/ubuntu/javaagent-example/hola.txt .
```

Remember destroy the pulumi stack to shutdown and remove the ec2 instance:

```bash
pulumi destroy
```
