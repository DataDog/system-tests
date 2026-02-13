## Requirements

### MacOS

Pulumi is infrastructure-as-code that allow you to manage AWS instance.

```sh
brew install pulumi/tap/pulumi
```

### Check if your AWS client is correctly configured


```sh
aws-vault exec sso-sandbox-account-admin -- aws s3 ls
```

* `credentials missing` -> Somebody (who? fresh-service?) needs to check that you belong to the good group in AWS
* need to `modify ~/.aws/config` ?

##  Run

* You need AppGate
* `./utils/scripts/ssi_wizards/aws_onboarding_wizard.sh`


## Miscs infos

* The account `Datadog - apm-ecosystems-reliability / 235494822917` is used in CIs, not locally
* The account `Datadog Sandbox / 601427279990` is used locally
* https://datadoghq.atlassian.net/wiki/spaces/APMINT/pages/3487138295/Using+virtual+machines+to+test+your+software+components+against+different+operating+systems#AWS-CLI%3A-Datadog-SandBox-Account
* https://system-tests.datadoghq.com/dashboard/nsk-tpd-u6q/aws-ec2-overview-system-tests?fromUser=false&refresh_mode=sliding&from_ts=1744813553852&to_ts=1744817153852&live=true
