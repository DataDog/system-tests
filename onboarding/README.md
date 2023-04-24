# Datadog Library Injection testing

Similarly to Library Injection in Kubernetes environments via the admission controller, Library injection simplifies the APM onboarding experience for customers deploying Java, NodeJS and .NET applications in VMs and docker environments.

The target of this testing feature is to test the distinct injection environments.

> Check Datadog lib injection capabilities [Official documentation](https://docs.datadoghq.com/tracing/trace_collection/library_injection/?tab=host).   

## Library Injection testing scenarios

The injection of libraries can take place in three scenarios:
* Datadog Agent and your application deployed on the same host.
* Datadog Agent installed on host and your application deployed on container.
* Datadog Agent and your application installed on containers.

> For Kubernetes Datadog library injection capabilities testing check [System-tests/lib-injection](https://github.com/DataDog/system-tests/tree/main/lib-injection).   

## Prerequisites

In order to test the execution of Datadog automatic injection software, we have to start up different types of virtual machines.

We will use:

* AWS as the infrastructure provider
* Pulumi as the orchestrator of this test infrastructure.
* Pytest as testing tool (Python)

### AWS

Configure your AWS account and AWS CLI. [Check documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html)

In order to securely store and access AWS credentials in an our test environment, we are using aws-vault. Please install and configure it. [Check documentation](https://github.com/99designs/aws-vault)

### Pulumi

Pulumi is a universal infrastructure as code platform that allows you to use familiar programming languages and tools to build, deploy, and manage cloud infrastructure.
Please install and configure as described in the [following documentation](https://www.pulumi.com/docs/get-started/aws/)

### Pytest

In order to build the final tests assertions we are using the framework [pytest](https://docs.pytest.org/en/7.2.x/)

## Test matrix

We want to test Datadog software in the three main scenarios described above, but bearing in mind these other conditions:

- We want to check the releases and the snapshot/beta of Datadog software:
    - Datadog Agent product
    - Library injection software
- We want to check Datadog software installed in different machine types or distint SO distributions (Ubuntu, Centos...)
- We want to check Datadog library injection software for different languages (Currently  supports for Java, Nodejs and dotNet)
    - We want to test the different versions of the supported languages (Java 8, Java 11). 

## Define your infraestructure

YML files define the AMI machines and software to be installed: 

- **provision_host.yml:** All software and the test applications installed on host.
- **provision_host_docker.yml:** Datadog Agent installed on host and your application deployed on container.
- **provision_docker.yml:** Datadog Agent installed on containers.

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
- **Autoinjection:** Grouped by language (Java, Nodejs, dotNet) and environment (prod/dev):
    ```
    autoinjection:
    - java: 
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
    ```
- **language-variants:** Especially useful in the scenario that does not contain containers. It will allow us to install different language versions:
    ```
    language-variants:
    - java: 
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
    ```

## Tests assertions

The testing process is very simple. For each machine started we will check:

- The weblog application is listenning on the common port.
- The weblog application is sending traces to Datadog backend.

Check the tests assertions from *tests/test_traces.py*

Check the pytest configuration from *conftest.py*

## Run the tests

### Configure secrets

You must configure datadog secrets. Run:

```
pulumi config set --secret ddagent:apiKey xxxyyyyzzzzz
pulumi config set --secret ddagent:appKey zzzzyyyyyxxx
```

### Run script

Before executing run script, you should create a Python virtual environment and install the Python dependencies from the onboarding tests directory:

```sh
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

There is a run script "run.sh" to which we have to pass the configuration parameters in order to create the infraeestructure and execute the tests. This is an example of a test launch:

`./run.sh --KeyPairName mykeypair --subnet subnet-zzzz --vpc sg-12345,sg-6789 --dd-site datadoghq.com --private-key-path /Users/user/mykeypair.pem --instance-type t2.micro`

> [Check the run.sh script usage details](USAGE.md)


