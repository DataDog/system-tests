1. [Datadog Library Injection testing](#Datadog-Library-Injection-testing)

   * [Library Injection testing scenarios](#Library-Injection-testing-scenarios)
   * [Knowledge concepts](#Knowledge-concepts)
     - [Define a Virtual Machine scenario](#Define-a-Virtual-Machine-scenario)
     - [Virtual Machine](#Virtual-Machine)
     - [Provision](#Provision)
     - [Provider](#Provider)
2. [Run the tests](#Run-the-tests)

   * [Prerequisites](#Prerequisites)
     - [AWS](#AWS)
     - [Vagrant](#Vagrant)
     - [Pulumi](#Pulumi)
     - [System-tests requirements](#System-tests-requirements)
   * [Configure the environment variables](#Configure-the-environment-variables)
   * [Run the scenario](#run-the-scenario)
3. [How to develop a test case](#How-to-develop-a-test-case)

   * [Folders and Files structure](#Folders-and-Files-structure)
   * [Implement a new test case](#Implement-a-new-test-case)
4. [How to debug your kubernetes environment and tests results](#How-to-debug-your-kubernetes-environment-and-tests-results)
5. [How to debug your kubernetes environment at runtime](#How-to-debug-your-kubernetes-environment-at-runtime)

# Datadog Library Injection testing

Similarly to Library Injection in Kubernetes environments via the admission controller, Library injection simplifies the APM onboarding experience for customers deploying Java, NodeJS, .NET and Ruby applications in VMs and docker environments.

The target of this testing feature is to test the distinct injection environments.

> Check Datadog lib injection capabilities [public documentation](https://docs.datadoghq.com/tracing/trace_collection/library_injection).

## Library Injection testing scenarios

The automatic libray injection is tested on two scenarios:

* Datadog Agent and your application deployed on the same host ([host injection documentation](https://docs.datadoghq.com/tracing/trace_collection/library_injection_local/?tab=host)).
* Datadog Agent deployed on the host, your application deployed on containers ([agent on host and app in containers documentation](https://docs.datadoghq.com/tracing/trace_collection/library_injection_local/?tab=agentonhostappincontainers)).
* Datadog Agent and your application installed on containers ([containers injection documentation](https://docs.datadoghq.com/tracing/trace_collection/library_injection_local/?tab=agentandappinseparatecontainers)).

> For Kubernetes Datadog library injection capabilities check the [kubernetes injection documentation](https://docs.datadoghq.com/tracing/trace_collection/library_injection_local/?tab=kubernetes) or take a look at the [kubernetes injection testing scenarios](https://github.com/DataDog/system-tests/blob/main/docs/scenarios/k8s_lib_injection.md).

## Knowledge concepts

We need to know some terms:

* **Scenario:** In system-tests, a virtual scenario is a set of:

  * a tested architecture, which can be a single virtual machine. This VM will be supplied thanks to the integration of system-tests framework with different providers of this technology.
  * a list of setup executed on this tested architecture, we called as a virtual machine provision. Each scenario is associated with a provision.
  * a list of test associated to a scenario
* **Virtual Machine:** A virtual machine (VM) is a replica, in terms of behavior, of a physical computer. There is software capable of emulating these replicas of physical computers running operating systems. In this case, system-tests will be able to handle the integration of the framework itself with the virtual machines, so that we can install our software to be tested on them (provision).
* **Provision:** It will be the list of software and configurations to be installed on the virtual machine. The provisions will be specified by using yaml files.
* **Weblog:** Usually It is a web application that exposes consistent endpoints across all implementations and that will be installed on the Virtual Machine. In the case of weblogs associated to the VMs, it does not always have to be a web application that exposes services, it can also be a specific configuration for the machine we want to test.
* **Provider:** It refers to the integration of system-tests with the different technologies that allow interacting with virtual machines. These can be executed locally using software such as vmware, virtual box... or executed in the cloud using services such as Google Cloud or AWS.
* **Tests:** Set of tests to run against a virtual machine. For example, we can make remote HTTP requests to an installed web application during the provisioning process or we can connect to it via SSH to execute different commands to check that the installed software provision is running correctly.

### Define a Virtual Machine scenario

You can create your own VirtualMachine scenario, specifing the allowed machines and the default provision-
In the following code you can see how we define a new VirtualMachine Scenario, setting the VMs that you want to run:

```Python
class InstallerAutoInjectionScenarioProfiling(_VirtualMachineScenario):
    """As Profiling is not included in GA (2024/11) we reduce the number of VMS to speed up the execution
    Until we fix the performance problems on the AWS architecture and speed up the tests
    """

    def __init__(
        self,
        name,
        doc,
        vm_provision="installer-auto-inject", #Reference to the provision for this scenario
        agent_env=None,
        app_env=None,
        scenario_groups=None,
        github_workflow=None,
    ) -> None:
        # Force full tracing without limits
        app_env_defaults = {
            "DD_TRACE_RATE_LIMIT": "1000000000000",
            "DD_TRACE_SAMPLING_RULES": "'[{\"sample_rate\":1}]'",
        }
        if app_env is not None:
            app_env_defaults.update(app_env)

        super().__init__(
            name,
            vm_provision=vm_provision,
            agent_env=agent_env,
            app_env=app_env_defaults,
            doc=doc,
            github_workflow=github_workflow,
            include_ubuntu_22_amd64=True,
            include_ubuntu_22_arm64=True,
            include_amazon_linux_2_amd64=True,
            include_amazon_linux_2_arm64=True,
            include_amazon_linux_2023_amd64=True,
            include_amazon_linux_2023_arm64=True,
            include_redhat_7_9_amd64=True,
            include_redhat_8_amd64=True,
            include_redhat_8_arm64=True,
            include_redhat_9_amd64=True,
            include_redhat_9_arm64=True,
            scenario_groups=scenario_groups,
        )
```

### Virtual Machine

The Virtual Machines are defined in utils/_context/virtual_machines.py.
There are some  predefined machines. For example:

```Python
class Ubuntu22amd64(_VirtualMachine):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            "Ubuntu_22_amd64",
            aws_config=_AWSConfig(ami_id="ami-007855ac798b5175e", ami_instance_type="t3.medium", user="ubuntu"),
            vagrant_config=_VagrantConfig(box_name="bento/ubuntu-22.04"),
            krunvm_config=None,
            os_type="linux",
            os_distro="deb",
            os_branch="ubuntu22_amd64",
            os_cpu="amd64",
            default_vm=False,
            **kwargs,
        )
```

### Provision

We call provision to the configurations applied or the software installed on the machines included in the scenario.

Some properties of the provisions in system-tests are as follows:

* They are defined in the Yaml files.
* They Yaml file will be located in the folder: utils/build/virtual_machine/provisions/<provision_name>
* The installation of the Weblog (weblog provision) is also defined on Yaml files, but will be located in a different folder: utils/build/virtual_machine/weblogs/<lang>/<weblog_name>
* Each provision is different, therefore, different installation steps may be defined.
* All provisions may define their own installation steps, but they must contain some mandatory definition steps. For example, all provisions will have to define a step that extracts  the names and versions of installed components we want to test.
* The same provision must be able to be installed on different operating systems and architectures.
* The selection of the provision to install in a virtual machine, is the responsibility of the python code that can be found at utils/virtual_machine/virtual_machine_provisioner.py

This is an example of provision file:

```yaml
#Optional: Load the environment variables
init-environment:
  #This variables will be populated as env variables in all commands for each provision installation
  - env: dev
    agent_repo_url: datad0g.com
    agent_dist_channel: beta
    agent_major_version: "apm"

  - env: prod
    agent_repo_url: datadoghq.com
    agent_dist_channel: stable
    agent_major_version: "7"


#Mandatory: Scripts to extract the installed/tested components (json {component1:version, component2:version})
tested_components:
  install:
    - os_type: linux
      os_distro: rpm
      remote-command: |
          echo "{'agent':'$(rpm -qa --queryformat '%{VERSION}-%{RELEASE}' datadog-agent)'}"
    - os_type: linux
      os_distro: deb
      remote-command: |
          version_agent=$((dpkg -s datadog-agent || true)  | grep Version  | head -n 1 )  && echo "{'agent':'${version_agent//'Version:'/}'}"

#Mandatory: Steps to install provision
provision_steps:
  - init-config #Very first machine action
  - my-cutom-extra-step #secod step
  - install-agent #Install the agent

init-config:
  cache: true
  install:
    - os_type: linux
      remote-command: echo "Hey! Hello!"

my-cutom-extra-step:
  cache: true
  install:
    - os_type: linux
      os_distro: rpm
      copy_files:
        - name: copy-service
          local_path: utils/build/test.service

        - name: copy-script
          local_path: utils/build/rpm-myservice.sh
      remote-command: sh rpm-myservice.sh

    - os_type: linux
      os_distro: deb
      copy_files:
        - name: copy-service
          local_path: utils/build/test.service

        - name: copy-script
          local_path: utils/build/deb-myservice.sh
      remote-command: sh deb-myservice.sh

install-agent:
  install:
    - os_type: linux
      remote-command: |
        REPO_URL=$DD_agent_repo_url DD_AGENT_DIST_CHANNEL=$DD_agent_dist_channel DD_AGENT_MAJOR_VERSION=$DD_agent_major_version bash -c "$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script_agent7.sh)"
```

Some of the sections listed above are detailed as follows:

* **init-environment:** They are variables that will be loaded depending on the execution environment (env=dev or env=prod). These variables will be populated in all commands executed on the machines.
* **tested_components:** This is a mandatory field. We should extract the components that we are testing. The result of the command should be a json string. As you can see the install section could be split by “os_type“ and “os_distro“ fields. You could define a command for all the machines or you could define commands by the machine type. The details of the "installation" field are explained later.
* **provision_steps:** In this section you must define the steps for the whole installation. In this case we have three steps:
  * init-config: Represent a step that will run the same command for all types of the linux machines.
  * my-custom-extra-step: We divide the command, one specific for debian machines and another specific for rpm machines. Notice that we have added directives that will copy local files to the remote machine. The details of the "installation" and “copy-files” fields are explained later.
  * install-agent: It represents the installation of the agent, valid for all Linux machines. Note that we are using the variables defined in the “init-environment“ section.

#### Provision install section

The install section will be part of all main sections of the provision (except the init-environment and provision_steps sections).

The install section provides us:

* The ability to execute remote commands.
* The ability to execute local commands.
* The ability to copy files from the local machine to remote VM.

```yaml
my-step:
  install:
    - os_type: linux
      os_distro: rpm #Run for rpm machines
      local-command: echo "This command will run on local"
      copy_files:
        - name: copy-this-file-to-home-folder-on-remote-machine
          local_path: utils/build/test.service
      remote-command: echo "This command will run on remote machine"
```

You can define a provision that can be installed on a different machine types, architectures or OS:

```yaml
my-step:
  install:
    - os_type: linux
      os_distro: rpm #Run for rpm machines
      local-command: echo "This command will run on local"
      copy_files:
        - name: copy-this-file-to-home-folder-on-remote-machine
          local_path: utils/build/test.service
      remote-command: echo "This command will run on a RPM based remote machine"

    - os_type: linux
      os_distro: deb #Run for deb machines
      local-command: echo "This command will run on local"
      copy_files:
        - name: copy-this-file-to-home-folder-on-remote-machine
          local_path: utils/build/test.service
      remote-command: echo "This command will run on a debian based remote machine"

    - os_type: linux
      os_distro: deb #Run for deb machines
      os_cpu: arm64 #Run only for arm based machines
      local-command: echo "This command will run on local"
      copy_files:
        - name: copy-this-file-to-home-folder-on-remote-machine
          local_path: utils/build/test.service
      remote-command: echo "This command will run on a debian based remote machine (only for arm64 architectures)"
```

### Provider

We currently support two providers:

* **Pulumi AWS:** Using Pulumi AWS we can create and manage EC2 instances.
* **Vagrant:** Vagrant enables users to create and configure lightweight, reproducible, and portable development local environments (Beta feature).

We can find the developed providers in the folder: utils/virtual_machine.
We can select the correct provider for out configured environment using the factory located on utils/virtual_machine/virtual_machine_provider.py.

# Run the tests

## Prerequisites

To run the onboarding test scenarios, we will use the following utilities:

* AWS as the infrastructure provider: We are testing onboarding installation scenarios on different types of machines and OS. AWS Cli must be configured on your computer in order to launch EC2 instances automatically.
* Vagrant as the infrastructure local provider: For local executions, we can use Vagrant instead of AWS EC2 instances.
* Pulumi as the orchestrator of this test infrastructure: Pulumi's open source infrastructure as code SDK enables you to create, deploy, and manage infrastructure on any cloud, using your favorite languages.
* Pytest as testing tool (Python): System-tests is built on Pytest.

### AWS

Configure your AWS account and AWS CLI. [Check documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html)

In order to securely store and access AWS credentials in an our test environment, we are using aws-vault. Please install and configure it. [Check documentation](https://github.com/99designs/aws-vault)

### Vagrant

The Vagrant support is a system-tests beta feature. To run the tests using the Vagrant provider, you should install:

* Install Vagrant Install Vagrant | Vagrant | HashiCorp Developer
* Install QEMU emulator: Download QEMU - QEMU
* Install python Vagrant plugin: python-vagrant
* Install Vagrant-QEMU provider: https://github.com/ppggff/vagrant-qemu

### Pulumi

Pulumi is a universal infrastructure as code platform that allows you to use familiar programming languages and tools to build, deploy, and manage cloud infrastructure.
Please install and configure as described in the [following documentation](https://www.pulumi.com/docs/get-started/aws/)

### System-tests requirements

All system-tests assertions and utilities are based on python and pytests. You need to prepare this environment before run the tests:

- Python and pytests environment as described: [configure python and pytests for system-tests](../../README.md#requirements).
- Ensure that requirements.txt is loaded (you can run "./build.sh -i runner")
- AWS Cli is configured
- Pulumi environment configured as described: [Get started with Pulumi](https://www.pulumi.com/docs/get-started/)
  - Execute "pulumi login" local step: [Pulumi login](https://www.pulumi.com/docs/reference/cli/pulumi_login/).

## Configure the environment variables

Before execute the "onboarding" tests you must configure some environment variables:

- **ONBOARDING_AWS_INFRA_SUBNET_ID:** AWS subnet id.
- **ONBOARDING_AWS_INFRA_SECURITY_GROUPS_ID:** AWS security groups id.
- **DD_API_KEY_ONBOARDING:** Datadog API key.
- **DD_APP_KEY_ONBOARDING:** Datadog APP key.

To debug purposes you can create and use your own EC2 key-pair. You can read this tutorial to do that: [Create a key pair for your Amazon EC2 instance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/create-key-pairs.html)
Once the key has been created, you can use it configuring the following environment variables:

- **ONBOARDING_AWS_INFRA_KEYPAIR_NAME:** Set key pair name to ssh connect to the remote machines.
- **ONBOARDING_AWS_INFRA_KEY_PATH:** Local absolute path to your keir-pair file (pem file).

Opcionally you can set extra parameters to filter the type of tests that you will execute:

- **ONBOARDING_FILTER_OS_DISTRO:** Test only on a machine type (for instance 'deb' or 'rpm')

## Run the scenario

The 'onboarding' tests can be executed in the same way as we executed system-tests scenarios.
The currently supported scenarios are the following:

* **SIMPLE_INSTALLER_AUTO_INJECTION:** The onboarding minimal scenario. The test makes a request to deployed weblog application and then check that the instrumentation traces are sending to the backend.
* **INSTALLER_AUTO_INJECTION:** Inlcudes the minimal scenario assertions but adding other assertions like the uninstall process or the block list commands tests.
* **INSTALLER_NOT_SUPPORTED_AUTO_INJECTION:** Onboarding Single Step Instrumentation scenario for not supported runtime language versions. After install the SSI software this scenario checks that the application is not auto instrumented (because the runtime version is not supported), but continues working.
* **CHAOS_INSTALLER_AUTO_INJECTION:** Onboarding Host Single Step Instrumentation scenario.
* **SIMPLE_AUTO_INJECTION_PROFILING:** Onboarding Single Step Instrumentation scenario with profiling activated by the app env var
* **HOST_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING:** Onboarding Host Single Step Instrumentation scenario using agent auto install script with profiling activating by the installation process
* **CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING:** Onboarding Container Single Step Instrumentation profiling scenario using agent auto install script
* **HOST_AUTO_INJECTION_INSTALL_SCRIPT:** Onboarding Host Single Step Instrumentation scenario using agent auto install script
* **CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT:** Onboarding Container Single Step Instrumentation scenario using agent auto install script


The 'onboarding' tests scenarios requiered three mandatory parameters:

- **--vm-library:** Configure language to test (currently supported languages are: java, python, nodejs, dotnet)
- **--vm-env:** Configure origin of the software: dev (beta software) or prod (releases)
- **--vm-weblog:** Configure weblog to tests
- **--vm-provider:** Default "aws"

The following line shows an example of command line to run the tests:

- './run.sh SIMPLE_HOST_AUTO_INJECTION --vm-weblog test-app-nodejs --vm-env dev --vm-library nodejs --vm-provider aws'
