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
| AWS SSI | AWS CLI, aws-vault, Pulumi 3.69 or later | AWS SSI account, AppGate, and keys for the system-tests Datadog organization |
| K8s library injection | Kind or Minikube, Helm | Private ECR access |
| K8s injector-dev | `injector-dev`, Colima, Minikube, Helm, kubectl | A private registry. Datadog ECR is the default |

The Kubernetes wizards can install the local Kubernetes tools. The
injector-dev wizard can also copy or download the `injector-dev` binary.

## Configure AWS access

AWS SSI and the Kubernetes test suites use different AWS accounts.

| Use | Account | aws-vault profile |
| --- | --- | --- |
| Run AWS SSI on EC2 | `dev-apm-dcs-system-tests` (`778997161346`) | `sso-dev-apm-dcs-system-tests-account-admin` |
| Use SSI images in ECR | `apm-ecosystems-reliability` (`235494822917`) | `sso-apm-ecosystems-reliability-account-admin` |

Follow the internal
[AWS SSO setup guide](https://datadoghq.atlassian.net/wiki/spaces/ENG/pages/2498068557/AWS+SSO+Getting+Started).
Use the current setup command:

```bash
ddtool cloud aws config
```

On macOS, install `aws-vault` with Homebrew:

```bash
brew install aws-vault
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

## Configure AppGate for AWS SSI

AWS SSI creates EC2 instances on a private network. AppGate lets your machine
reach those instances.

AppGate grants this access by Datadog team. Your user must belong to at least
one of these teams:

- Cloud Networks
- Ecosystems Reliability
- Injection Platform
- Onboarding & Enablement
- Language Platform

The
[AppGate entitlement file](https://github.com/ddoghq/appgate/blob/7c8743702a11ef4909cabcc927e3063f893d71bb/prod-6.5-003-main-configuration-vpn-services-commercial-site-dev-apm-dcs-system-tests-entitlements/dev-apm-dcs-system-tests.tf)
is the source for this list. If your team is missing, ask in
[#apm-shared-testing](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X).
The maintainers can request an entitlement update. See
[ddoghq/appgate#2633](https://github.com/ddoghq/appgate/pull/2633) for an
example.

1. Open the internal
   [AppGate client profile page](https://datadoghq.atlassian.net/wiki/spaces/IRFCN/pages/7405273906/AppGate+Client+Profile+Links).
2. Add the **Commercial Green** profile to the AppGate client.
3. Connect to **Commercial Green** before you run the AWS SSI wizard.

Do not copy AppGate profile links into this repository. The internal page owns
and updates those links.

If AppGate cannot connect, use the internal
[AppGate troubleshooting guide](https://datadoghq.atlassian.net/wiki/spaces/IRFCN/pages/4937288309/Appgate+Troubleshooting).

## Configure AWS SSI secrets

The AWS SSI wizard asks for:

- `PULUMI_CONFIG_PASSPHRASE`
- `DD_API_KEY_ONBOARDING`
- `DD_APP_KEY_ONBOARDING`

The Datadog keys must belong to the
[system-tests Datadog organization](https://system-tests.datadoghq.com/).
If you cannot create or read these keys, ask in
[#apm-shared-testing](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X).

The wizard can save the values in the local `.env` file. Git ignores this file.
Never add these values to source files or commits.

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
