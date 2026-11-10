# SSI access and prerequisites

Use this page before you run an SSI wizard. For the commands, see the
[SSI quick start](ssi.md).

## Common requirements

All SSI test suites need:

- Bash
- Git
- Docker 20.10 or later
- Python 3.12

Run commands from the root of the system-tests repository.

Each wizard prepares the system-tests Python environment. You can also prepare
it before you start:

```bash
./build.sh -i runner
```

Check that Docker is running:

```bash
docker info
```

## Requirements by test suite

| Test suite | Extra tools | Access |
| --- | --- | --- |
| Docker SSI | None for most tests | Private ECR access only for `websphere-app` and `jboss-app` |
| AWS SSI | AWS CLI, aws-vault, and Pulumi 3.69 or later | AWS account, AppGate, and Datadog keys |
| K8s library injection | AWS CLI, aws-vault, kubectl, Kind or Minikube, and Helm | Private ECR. Operator also needs Datadog keys |
| K8s injector-dev | `injector-dev`, Colima, Minikube, Helm, kubectl | A private registry. Datadog ECR is the default |

The K8s library injection wizard can install Kind or Minikube and Helm. It does
not install kubectl. Install kubectl before you start.

On macOS:

```bash
brew install kubectl
kubectl version --client
```

For other systems, follow the
[kubectl installation guide](https://kubernetes.io/docs/tasks/tools/#kubectl).

The injector-dev wizard can install its Kubernetes tools. It can also copy or
download the `injector-dev` binary.

## Configure AWS access

AWS SSI and the Kubernetes test suites use different AWS accounts.

| Use | Account | aws-vault profile |
| --- | --- | --- |
| Run AWS SSI on EC2 | `dev-apm-dcs-system-tests` | `sso-dev-apm-dcs-system-tests-account-admin` |
| Use SSI images in ECR | `apm-ecosystems-reliability` | `sso-apm-ecosystems-reliability-account-admin` |

Follow the internal
[AWS SSO setup guide](https://datadoghq.atlassian.net/wiki/spaces/ENG/pages/2498068557/AWS+SSO+Getting+Started).
Use the current setup command:

```bash
ddtool cloud aws config
```

On macOS, install the AWS CLI and `aws-vault` with Homebrew:

```bash
brew install awscli aws-vault
```

For other systems, use the installation steps in the AWS SSO setup guide.

Check AWS SSI access:

```bash
aws-vault exec sso-dev-apm-dcs-system-tests-account-admin -- aws sts get-caller-identity
```

Check ECR access:

```bash
aws-vault exec sso-apm-ecosystems-reliability-account-admin -- \
  aws ecr get-login-password --region us-east-1 >/dev/null
```

If a profile is missing, run `ddtool cloud aws config` again. If the account is
still missing, use the
[Cloud Access request form](https://datadoghq.atlassian.net/jira/software/c/projects/CLOUDA/forms/form/direct/4/26949).
Ask for access to the account and profile from the table above.

## Configure network access for AWS SSI

AWS SSI creates EC2 instances on a private network. Datadog employees need
access to that network through AppGate.

The access rules and client profiles are internal. They can also change. Do
not copy them into this public repository.

Before your first run, ask in
[#apm-shared-testing](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X)
for the current setup steps. The maintainers can confirm that your Datadog team
has access and give you the current client profile.

Connect to the Datadog private network before you run the AWS SSI wizard.

## Configure Datadog keys

AWS SSI and `K8S_LIB_INJECTION_OPERATOR` use the real Datadog backend. Both
need:

- `DD_API_KEY_ONBOARDING`
- `DD_APP_KEY_ONBOARDING`

The Datadog keys must belong to the
[system-tests Datadog organization](https://system-tests.datadoghq.com/).
If you cannot create or read these keys, ask in
[#apm-shared-testing](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X).

The AWS SSI wizard asks for these keys. It also asks for
`PULUMI_CONFIG_PASSPHRASE`. The wizard can save all three values in the local
`.env` file.

For the K8s Operator scenario, add the two Datadog keys to `.env` before you
run the wizard:

```text
DD_API_KEY_ONBOARDING=<api-key>
DD_APP_KEY_ONBOARDING=<application-key>
```

Git ignores `.env`. Never add these values to source files or commits.

The wizard provides working defaults for the subnet, security group, and IAM
instance profile. Use those defaults for a normal local run.

An EC2 key pair is optional. Use the default option unless you need SSH access
to debug the virtual machine.

## Configure the private ECR registry

K8s library injection always uses the private Datadog ECR registry. K8s
injector-dev can use that registry or another private registry.

Docker SSI uses public images in most cases. These two weblogs use private ECR
images:

- `websphere-app`
- `jboss-app`

The wizards perform the ECR login. They use this registry:

```text
235494822917.dkr.ecr.us-east-1.amazonaws.com
```

ECR tokens expire. Run the wizard again to get a new token.

## Next steps

- [Choose and run an SSI test suite](ssi.md)
- [AWS SSI reference](../understand/scenarios/onboarding.md)
- [Docker SSI reference](../understand/scenarios/docker_ssi.md)
- [K8s library injection reference](../understand/scenarios/k8s_lib_injection.md)
- [K8s injector-dev reference](../understand/scenarios/k8s_injector_dev.md)
