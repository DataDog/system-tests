# Datadog Library Injection testing

Similarly to Library Injection in Kubernetes environments via the admission controller, this simplifies the APM onboarding experience for customers deploying Java, NodeJS and .NET applications in VMs and docker environments.

The target of this testing feature is to test the distinct injection environments.

## PREREQUISITES

In order to test the execution of our automatic injection software, we have to start different types of virtual machines.

We will use:

* AWS as the infrastructure provider
* Pulumi as the orchestrator of this test infrastructure.
* Pytest as testing tool (Python)

### AWS

Configure your AWS account and AWS CLI. [Check documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html)

In order to securely store and access AWS credentials in an our test environment, we are using aws-vault. Please install and configure it. [Check documentation](https://github.com/99designs/aws-vault)

### PULUMI

Pulumi is a universal infrastructure as code platform that allows you to use familiar programming languages and tools to build, deploy, and manage cloud infrastructure.
Please install and configure as described in the [following documentation](https://www.pulumi.com/docs/get-started/aws/)

### PYTEST

In order to build the final tests assertions we are using the framework [pytest](https://docs.pytest.org/en/7.2.x/)

## YOUR INFRASTRUCTURE

Check the AMI machines and software to be installed on them from the yml file: provision.yml

## YOUR SAMPLE APPLICATION

You can found your sample applications (weblogs) grouped by programming language on the folder: weblog/

## YOUR TESTS ASSERTIONS

Check your tests assertions from tests/test_traces.py

Check your pytest configuration from conftest.py

## RUN THE TESTS

### Configure secrets

You must configure datadog secrets. Run:

```
pulumi config set --secret ddagent:apiKey xxxyyyyzzzzz
pulumi config set --secret ddagent:appKey zzzzyyyyyxxx
```

### Run script

There is a run script "run.sh" to which we have to pass the configuration parameters:

* --KeyPairName: Key pair name. See [Amazon EC2 Key pair](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html)
* --subnet: AWS subnet id
* --vpc: AWS VPC groups id (separated by comma)
* --dd-site: Datadog backend url (example datadoghq.com)
* --private-key-path: Path to your local perm file. See [AWS create key pairs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/create-key-pairs.html)
* --instance-type: Type of Amazon EC2 instance. See [AWS EC2 Instance Types](https://aws.amazon.com/ec2/instance-types/)

This is an example of a test launch:

`./run.sh --KeyPairName mykeypair --subnet subnet-zzzz --vpc sg-12345,sg-6789 --dd-site datadoghq.com --private-key-path /Users/user/mykeypair.pem --instance-type t2.micro`
