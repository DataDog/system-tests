# Run SSI tests

SSI means Single Step Instrumentation. It installs and injects a Datadog tracer
without changes to the application code.

This page covers all local SSI test suites in system-tests.

## Choose a test suite

| Test suite | Use it to test | Runs on | Validation |
| --- | --- | --- | --- |
| Docker SSI | Tracer versions, guardrails, service naming, and other fast checks | Local Docker | APM Test Agent |
| AWS SSI | Host and container injection on real virtual machines | AWS EC2 | Datadog backend |
| K8s library injection | Admission Controller, injector, lib-init, and Cluster Agent | Local Kind or Minikube | APM Test Agent |
| K8s injector-dev | Changes to the `injector-dev` tool | Local Colima and Minikube | APM Test Agent |

If you are new to SSI, start with Docker SSI. It has the fewest access
requirements.

Use K8s library injection for normal Kubernetes injection tests. Use K8s
injector-dev only when your change depends on the `injector-dev` tool.

## Terms used on this page

- **Scenario:** The test environment, its configuration, and its tests.
- **Weblog:** A sample application that system-tests instruments.
- **Wizard:** An interactive script that selects a valid test combination.
- **Tracer:** The Datadog library injected into the application.
- **APM Test Agent:** A local test service that captures telemetry.
- **Injector:** The component that adds the tracer to an application.
- **lib-init:** A container image that holds one tracer library.
- **Cluster Agent:** The Datadog component that runs the Admission Controller.
- **Admission Controller:** A component that changes a pod before it starts.
- **ECR:** The AWS container image registry used by these tests.
- **Provision:** The software and commands that AWS SSI installs on a virtual machine.

AWS SSI is also called **onboarding**, **auto-injection**, or
**auto-instrumentation** in this repository.

## Before you start

You need Bash, Git, Docker 20.10 or later, and Python 3.12.

Read the [SSI access and prerequisites guide](ssi-access.md). It covers AWS
profiles, private network access, ECR, Pulumi, Kubernetes tools, and Datadog
keys.

Run every command from the root of the system-tests repository.

## Docker SSI

Docker SSI is the fastest SSI test suite. Most test cases use public images.

Run the wizard:

```bash
./utils/scripts/ssi_wizards/docker_ssi_wizard.sh
```

The wizard selects a language, scenario, weblog, base image, architecture, and
runtime. It prints the final `./run.sh` command before it starts.

The `websphere-app` and `jboss-app` weblogs need private ECR access. The wizard
can perform that login.

See the [Docker SSI reference](../understand/scenarios/docker_ssi.md) for the
manual command and development details.

## AWS SSI

AWS SSI creates an EC2 instance and installs SSI on it. It sends telemetry to
the system-tests Datadog organization.

Complete the [AWS access steps](ssi-access.md#configure-aws-access) and the
[network access steps](ssi-access.md#configure-network-access-for-aws-ssi).
Connect to the Datadog private network before you start.

Run the wizard:

```bash
./utils/scripts/ssi_wizards/aws_onboarding_wizard.sh
```

The wizard checks Pulumi and AWS access. It also configures the local `.env`
file. You then select a language, scenario, weblog, virtual machine, and
released or development components.

The wizard shuts down the EC2 instance after the run. If you keep the instance
for debugging, follow its `pulumi destroy` reminder.

See the [AWS SSI reference](../understand/scenarios/onboarding.md) for manual
execution, logs, and troubleshooting.

## K8s library injection

This suite tests the normal Kubernetes library injection flow. It uses the
Datadog Admission Controller or pod annotations.

Complete the ECR steps in the
[access guide](ssi-access.md#configure-the-private-ecr-registry).

Run the wizard:

```bash
./utils/scripts/ssi_wizards/k8s_ssi_wizard.sh
```

The wizard installs the system-tests runner. It can also install Kind,
Minikube, and Helm. You then select the scenario, weblog, and component
versions.

See the
[K8s library injection reference](../understand/scenarios/k8s_lib_injection.md)
for manual execution, component versions, logs, and debugging.

## K8s injector-dev

This suite tests the `injector-dev` binary. It is not the default K8s SSI test
suite.

Complete the injector-dev steps in the
[access guide](ssi-access.md#requirements-by-test-suite).

Run the wizard:

```bash
./utils/scripts/ssi_wizards/k8s_injector_dev_wizard.sh
```

The wizard checks the binary and the local Kubernetes tools. It then
configures a private registry and selects the test components.

See the [K8s injector-dev reference](../understand/scenarios/k8s_injector_dev.md)
for manual execution and all command options.

## Read the result

The terminal shows the pytest result. A successful run ends with exit code
zero.

Each scenario writes its files to a folder such as `logs_docker_ssi`. The
folder name uses the scenario name in lowercase. Use these pages:

- [Test outcomes](test-outcomes.md)
- [Log files](logs.md)
- [General troubleshooting](troubleshooting.md)
- [AWS SSI troubleshooting](../understand/scenarios/onboarding.md#troubleshooting)
- [K8s logs](../understand/scenarios/k8s_lib_injection.md#how-to-debug-your-kubernetes-environment-and-tests-results)

If you are still blocked, ask in
[#apm-shared-testing](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X).
