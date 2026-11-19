# K8s Library Injection

* For first runs, use the [SSI quick start](../../docs/execute/ssi.md) and
  [SSI access guide](../../docs/execute/ssi-access.md).
* K8s library injection and K8s injector-dev are different test suites. Use
  [the overview](../../docs/understand/scenarios/k8s_library_injection_overview.md)
  to choose one.
* Run normal K8s library injection with
  `utils/scripts/ssi_wizards/k8s_ssi_wizard.sh`. Use
  [the K8s guide](../../docs/understand/scenarios/k8s_lib_injection.md) for
  manual commands.
* Run K8s injector-dev with
  `utils/scripts/ssi_wizards/k8s_injector_dev_wizard.sh`. Use
  [the injector-dev guide](../../docs/understand/scenarios/k8s_injector_dev.md)
  for manual commands.
* After add a new K8s Lib Injection scenario, you must declare it in utils/scripts/ci_orchestrators/k8s_ssi.json, to allow to create the tests matrix for CI and for the wizard.
* After add a new K8s injector dev scenario, you must declare it in utils/scripts/ci_orchestrators/k8s_injector_dev.json, to allow to create the tests matrix for CI and for the wizard.
* After add a new K8s Lib Injection weblog, you must declare it in utils/scripts/ci_orchestrators/k8s_ssi.json, to allow to create the tests matrix for CI and for the wizard.
* After add a new K8s injector dev weblog, you must declare it in utils/scripts/ci_orchestrators/k8s_injector_dev.json, to allow to create the tests matrix for CI and for the wizard.
* If your response about Kubernetes (k8s) includes an explanation of how to use a private container registry, make sure to provide examples of: 1) how to authenticate/login with AWS ECR using Vault (docker login). 2) how to set the env variable PRIVATE_DOCKER_REGISTRY. 3) How to set the env variable PRIVATE_DOCKER_REGISTRY_USER. 4) How to set the env variable PRIVATE_DOCKER_REGISTRY_TOKEN using the aws-vault and the 'aws ecr get-login-password' command.
