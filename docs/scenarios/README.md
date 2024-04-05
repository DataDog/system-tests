In system-tests, a scenario is a set of:

* a tested architecture, which can be a set of docker containers, a single container, or even nothing
* a list of setup executed on this tested architecture
* and a list of test

## How to identify a scenario?

Every scenarios are identified by an unique identifier in capital letter, like `APPSEC_IP_BLOCKING_FULL_DENYLIST`. To specify a scenario, simply use its name after `run.sh`:

```bash
./run.sh APPSEC_IP_BLOCKING_FULL_DENYLIST
```

If no scenario is specified, the `DEFAULT` scenario is executed.

## How to define a tested architecture?

Scenario's architecture is defined in python, in the file `utils/_context/scenarios.py`. Most of them are based on `EndToEndScenario` class. It spwans a container with an weblog (shipping a datadog tracer), an container with an datadog agent, and a proxy that spies everything coming from tracer and agent. Optionnaly, some other containers can be added (mostly databases).

## How to define setup?

A setup is a class method with the same name of a test method. They are all executed before any test starts. If a test is not executed (whatever the reason), the setup method won't be executed.

## How to define test executed by a scenario

The `scenarios` singleton is available under `utils` module. It exposes decorators with  all possible scenarios. Simply decorate your test class/method with it :

```python
@scenarios.my_scenario
class Test_Something:
    ...
```

## Scenarios

### End to end scenarios

Based on class `EndToEndScenario`, they spwan a weblog (HTTP app shipping a tracer), an agent, a proxy between tracer-agent-backend, and run a set of high level functionnal tests. The `DEFAULT` scenario is the main scenario of system tests, and is in this family.

### Parametric scenario

Parametric scenario build and spawn a tracer with a simple GRPC interface. It's not really unit tests (still black-box testing), neither functionnal tests (only tracers are tested), they are convenient to tests different parameter set for tracers. More detailled documentation can be found [here](https://github.com/DataDog/system-tests/blob/main/docs/scenarios/parametric.md).

### Auto-Inject/OnBoarding scenarios

Automatic library injection simplifies the APM onboarding experience for customers deploying Java, NodeJS, .NET, Python and Ruby applications in VMs and docker environments. Datadog software installed on the machine will be intercept the startup of your application and it will inject the tracer library automatically. The OnBoarding scenarios reproduce different environments and check the library injection is done correctly. More detailled documentation can be found [here](https://github.com/DataDog/system-tests/blob/main/docs/scenarios/onboarding.md).

### Kubernetes Auto-Inject scenarios

The lib-injection project is a feature to allow injection of the Datadog library into a customer's application container without requiring them to modify their application images.

This feature enables applications written in Java, Node, Python, DotNet or Ruby running in Kubernetes to be automatically instrumented with the corresponding Datadog APM libraries. More detailled documentation can be found [here](https://github.com/DataDog/system-tests/blob/main/docs/scenarios/k8s_lib_injection.md).