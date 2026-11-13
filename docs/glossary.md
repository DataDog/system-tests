# Glossary

## SSI and library injection

- **Single Step Instrumentation (SSI):** Installs and injects a Datadog tracer
  without application code changes.
- **Auto-instrumentation / auto-injection / library injection:** Other names
  for the SSI process.
- **AWS SSI / onboarding:** Tests host and container injection on EC2 virtual
  machines.
- **Docker SSI:** Runs fast SSI checks in local Docker containers.
- **K8s library injection:** Tests injection into applications that run in a
  local Kubernetes cluster.
- **K8s injector-dev:** Tests library injection through the `injector-dev`
  tool.
- **Scenario:** The test environment, its configuration, and its tests.
- **Weblog:** A sample application that system-tests instruments.
- **Wizard:** An interactive script that selects a valid test combination.
- **Tracer:** A Datadog library that instruments an application.
- **APM Test Agent:** A local service that captures test telemetry instead of
  sending it to the Datadog backend.
- **Injector:** The component that adds the tracer to an application.
- **lib-init:** A container image that holds one tracer library.
- **Cluster Agent:** The Datadog component that runs the Admission Controller.
- **Admission Controller:** A component that can change a Kubernetes pod
  before it starts.
- **Provision:** The software and commands that AWS SSI applies to a virtual
  machine.
- **Provider:** The system that creates and manages a virtual machine.
- **AMI cache:** Reusable AWS machine images that shorten AWS SSI setup.
- **ECR:** The AWS container registry used for private SSI images.

## Test activation/deactivation

- **Successful:** All test assertions pass.
- **Unsuccessful:** At least one test assertion fails.
- **Enabled:** An unsuccessful result fails the test run.
- **Disabled:** The test has a `bug`, `missing_feature`, `flaky`,
  `irrelevant`, or `incomplete_test_app` marker. Its result does not fail the
  test run.
- **Pass:** The test is enabled and successful.
- **Fail:** The test is enabled and unsuccessful.
- **Xpass:** The test is disabled but successful. It may be ready to enable.
- **Xfail:** The test is disabled and unsuccessful. The test still runs.
- **Skipped:** The test does not run. Some `irrelevant`, `flaky`, `@slow`, or
  `@scenario_crash` declarations cause this result.
- **Easy win:** Another name for an xpass.
