# Datadog Library Injection testing

Similarly to Library Injection in Kubernetes environments via the admission controller, Library injection simplifies the APM onboarding experience for customers deploying Java, NodeJS, .NET and Ruby applications in VMs and docker environments.

The target of this testing feature is to test the distinct injection environments.

> Check Datadog lib injection capabilities [public documentation](https://docs.datadoghq.com/tracing/trace_collection/library_injection).   

## Library Injection testing scenarios

The automatic libray injection is tested on two scenarios:
* Datadog Agent and your application deployed on the same host ([host injection documentation](https://docs.datadoghq.com/tracing/trace_collection/library_injection/?tab=host)).
* Datadog Agent and your application installed on containers ([containers injection documentation](https://docs.datadoghq.com/tracing/trace_collection/library_injection/?tab=agentandappinseparatecontainers)).

> For Kubernetes Datadog library injection capabilities testing check [System-tests/lib-injection](https://github.com/DataDog/system-tests/blob/main/lib-injection/README.md).   

## Prerequisites

To test scenarios mentioned above, We will use the following utilities:

* AWS as the infrastructure provider: We are testing onboarding installation scenarios on different types of machines and OS. AWS Cli must be configured on your computer in order to launch EC2 instances automatically.
* Pulumi as the orchestrator of this test infrastructure: Pulumi's open source infrastructure as code SDK enables you to create, deploy, and manage infrastructure on any cloud, using your favorite languages.
* Pytest as testing tool (Python): System-tests is built on Pytest.

### AWS

Configure your AWS account and AWS CLI. [Check documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html)

In order to securely store and access AWS credentials in an our test environment, we are using aws-vault. Please install and configure it. [Check documentation](https://github.com/99designs/aws-vault)

### Pulumi

Pulumi is a universal infrastructure as code platform that allows you to use familiar programming languages and tools to build, deploy, and manage cloud infrastructure.
Please install and configure as described in the [following documentation](https://www.pulumi.com/docs/get-started/aws/)

### Pytest

All system-tests assertions and utilities are based on python and pytests. Check the documentation to configure your python environment: [system-tests requirements](https://github.com/DataDog/system-tests/blob/main/docs/execute/requirements.md)

## Test matrix

We want to test Datadog software on the two main scenarios described above, but keeping in mind other conditions:

- We want to check the releases and the snapshot/beta versions of Datadog library injection software.
- We want to check Datadog software installed in different machine types or distint SO distributions (Ubuntu, Centos...)
- We want to check Datadog library injection software for different languages (Currently  supports for Java, Python, Nodejs, dotNet and Ruby)
    - We want to test the different versions of the supported languages (Java 8, Java 11). 

## Define your infraestructure

YML files define the AMI machines and software to be installed (folder tests/onboarding/infra_provision/): 

- **provision_onboarding_host_<lang>.yml:** All the software and the test applications installed on host.
- **provision_onboarding_container_<lang>.yml:** Datadog Agent and the application installed on separated containers.

We have also auxiliary YML files with common parts used by any languages and any scenarios:

- **provision_ami.yml:** List of AMI (Amazon Machine Image) to be tested on host scenarios.
- **provision_ami_container.yml:**  List of AMI to be tested on container scenarios.
- **provision_agent_container.yml:** Installation process for agent deployed on docker container.
- **provision_agent.yml:** Installation process for agent deployed on host.
- **provision_init_vm_config.yml:** Proccess to be executed when the EC2 machine starts. For example, add linux users.
- **provision_installation_checks.yml:** Extract versions of the software that has been installed.
- **provision_prepare_docker.yml:** Docker installation process.
- **provision_prepare_repos.yml:** Prepare Datadog Linux repositories to download and install DD packages.

### Understanding YML files

There are some main sections that they will be combined in order to create a test matrix:

- **AMI:** Define AWS machine types (Ubuntu AMI, Linux Amazon...)
    - In this section we define the AMI id, and we categorize the machines by os_type, os_distro, os_branch:
    ```
    - name: ubuntu-x86-18.04
      ami_id: ami-0263e4deb427da90e
      user: ubuntu
      os_type: linux
      os_distro: deb

    - name: amazon-linux-x86
      ami_id: ami-0dfcb1ef8550277af
      user: ec2-user
      os_type: linux
      os_distro: rpm

    - name: amazon-linux-dotnet
      ami_id: ami-005b11f8b84489615
      user: ec2-user
      os_type: linux
      os_distro: rpm
      os_branch: amazon-netcore6
     ```
- **Agent:** Grouped by environment (prod for agent last release, dev for last snapshot/beta software). We can have distinc installation methods for each different os_type or os_distro. In this case we are going to use the universal linux installer:
    ```
    agent:
      - env: prod
        install:
          - os_type: linux
            command: bash -c "$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script_agent7.sh)"
    ```
- **Autoinjection:** Grouped by language (Java, Python, Nodejs, dotNet) and environment (prod/dev):
    ```
    autoinjection:
        - env: dev
          install: 
            - os_type: linux
              os_distro: deb
              command: |
                sudo apt install -y -t beta datadog-apm-inject datadog-apm-library-java
                dd-host-install

            - os_type: linux
              os_distro: rpm
              command: |          
                sudo yum -y install --disablerepo="*" --enablerepo="datadog-staging" datadog-apm-inject datadog-apm-library-java
                dd-host-install
          uninstall: 
            - os_type: linux 
              command: dd-host-install --uninstall
        - env: prod
          install: 
            - os_type: linux
              os_distro: deb
              command: |
                sudo apt install -y -t stable datadog-apm-inject datadog-apm-library-java
                dd-host-install

            - os_type: linux
              os_distro: rpm
              command: |
                sudo yum -y install --disablerepo="*" --enablerepo="datadog-stable" datadog-apm-inject datadog-apm-library-java
                dd-host-install
          uninstall: 
            - os_type: linux 
              command: dd-host-install --uninstall
    ```
- **language-variants:** Specially useful in the scenario that does not contain containers. This section is not mandatory. It will allow us to install different language versions:
    ```
    language-variants:
        - name: OpenJDK11
          version: 11
          install: 
            - os_type: linux
              os_distro: deb
              command: sudo apt-get -y install openjdk-11-jdk-headless

            - os_type: linux
              os_distro: rpm
              command: sudo amazon-linux-extras install java-openjdk11
    ```
- **weblogs:** In this section we will define the installation process of the different test applications, grouped by language. We can use existing applications in system-tests or download some from third parties. In the following example we use the sample application from the lib-injection folder and we also define the installation of WildFly as another sample application:
    ```
        weblogs:
          - java: 

              - name: test-app-java
                supported-language-versions:
                  - 11
                local-script: weblog/java/test-app-java/test-app-java_local_build.sh
                install: 
                   - os_type: linux
                     copy_files:
                        - name: copy-service
                          local_path: weblog/java/test-app-java/test-app-java.service
                          remote_path: test-app-java.service
    
                        - name: copy-run-weblog-script
                          local_path: weblog/java/test-app-java/test-app-java_run.sh
                          remote_path: test-app-java_run.sh

                        - name: copy-binary
                          local_path: ../lib-injection/build/docker/java/dd-lib-java-init-test-app/build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar 
                          remote_path: k8s-lib-injection-app-0.0.1-SNAPSHOT.jar  

                     command: sh test-app-java_run.sh
                uninstall: 
                  - os_type: linux
                    command: sudo systemctl stop test-app-java.service
              - name: wildfly
                supported-language-versions:
                   - 11
                install: 
                  - os_type: linux
                    copy_files:
                      - name: copy-service
                        local_path: weblog/java/wildfly/wildfly.service
                        remote_path: wildfly.service

                      - name: copy-run-weblog-script
                        local_path: weblog/java/wildfly/wildfly_run.sh
                        remote_path: wildfly_run.sh

                    command: sh wildfly_run.sh
                uninstall: 
                  - os_type: linux
                    command: sudo systemctl stop wildfly.service
    ```
The node "supported-language-versions" is not mandatory, in case it is specified the tests of this weblog will be associated to the installation of the language variant. 

## Tests assertions

The testing process is very simple. For each machine started we will check:

- The weblog application is listenning on the common port.
- The weblog application is sending traces to Datadog backend.

Check the tests assertions from *tests/test_onboarding_install.py*

For uninstall test scenarios, we are going to check the following rules after uninstall DD automatic library injection software:

- The weblog application is listenning on the common port.
- The weblog application is NOT sending traces to Datadog backend (The tracer library is not injected in the application).

## Run the tests

### Before run

Before run the onboarding tests you should configure:

- Python environment as described: [configure python for system-tests](https://github.com/DataDog/system-tests/blob/main/docs/execute/requirements.md).
- Ensure that requirements.txt is loaded (you can run "./build.sh -i runner")
- AWS Cli is configured
- Pulumi environment configured as described: [Get started with Pulumi](https://www.pulumi.com/docs/get-started/)
  - Execute "pulumi login" local step: [Pulumi login](https://www.pulumi.com/docs/reference/cli/pulumi_login/).

### Configure environment

Before execute the "onboarding" tests you must configure some environment variables:

- **ONBOARDING_AWS_INFRA_SUBNET_ID:** AWS subnet id.
- **ONBOARDING_AWS_INFRA_SECURITY_GROUPS_ID:** AWS security groups id. 
- **DD_API_KEY_ONBOARDING:** Datadog API key.
- **DD_APP_KEY_ONBOARDING:** Datadog APP key.
- **ONBOARDING_FILTER_ENV:** Posible values are 'dev' or 'prod'. You can select the software to be tested, latest releases or latest snapshots.
- **ONBOARDING_FILTER_WEBLOG:** Weblog to be tested.

To debug purposes you can create and use your own EC2 key-pair. To use it you should configure the following environment variables:

- **ONBOARDING_AWS_INFRA_KEYPAIR_NAME:** Set key pair name to ssh connect to the remote machines.
- **ONBOARDING_AWS_INFRA_KEY_PATH:** Local absolute path to your keir-pair file (pem file). 

Opcionally you can set extra parameters to filter the type of tests that you will execute:

- **ONBOARDING_FILTER_OS_DISTRO:** Test only on a machine type (for instance 'deb' or 'rpm')

### Run script

The 'onboarding' tests can be executed in the same way as we executed system-tests scenarios. 
The currently supported scenarios are the following:

* Test DD software on host using manual install (configuring linux repositories and installing DD packages one by one): 
  - ONBOARDING_HOST
  - ONBOARDING_HOST_UNINSTALL

* Test DD software on host using agent installation script: 
  - ONBOARDING_HOST_AUTO_INSTALL
  - ONBOARDING_HOST_AUTO_INSTALL_UNINSTALL

* Test DD software on container using manual install (configuring linux repositories and installing DD packages one by one): 
  - ONBOARDING_CONTAINER
  - ONBOARDING_CONTAINER_UNINSTALL

* Test DD software on container using agent installation script:
  - ONBOARDING_CONTAINER_AUTO_INSTALL
  - ONBOARDING_CONTAINER_AUTO_INSTALL_UNINSTALL

The 'onboarding' tests scenarios requiered three mandatory parameters:

- **--obd-library**: Configure language to test (currently supported languages are: java, python, nodejs, dotnet)
- **--obd-env**: Configure origin of the software: dev (beta software) or prod (releases)
- **--obd-weblog**: Configure weblog to tests 

The following line shows an example of command line to run the tests:

- './run.sh ONBOARDING_HOST --obd-weblog test-app-nodejs --obd-env dev --obd-library nodejs'
