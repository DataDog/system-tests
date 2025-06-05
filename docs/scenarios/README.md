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

Scenario's architecture is defined in python, in the file `utils/_context/scenarios/__init__.py`. Most of them are based on `EndToEndScenario` class. It spwans a container with an weblog (shipping a datadog tracer), an container with an datadog agent, and a proxy that spies everything coming from tracer and agent. Optionnaly, some other containers can be added (mostly databases).

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

System-tests contains various testing scenarios; the two most commonly used are called "End-To-End" and "Parametric."

### End to end scenarios

Based on class `EndToEndScenario`, they spwan a "weblog" HTTP server designed to mimick customer applications with automatic instrumentation, a "test-agent" to mimick the Datadog Agent, and communication with the Datadog backend via a proxy. The `DEFAULT` scenario is the main scenario of system tests, and is in this family.

End-To-End scenarios are good for testing real-world scenarios — they support the full lifecycle of a trace (hence the name, "End-To-End"). Use End-To-End scenarios to test tracing integrations, security products, profiling, dynamic instrumentation, and more. When in doubt, use end-to-end.

### Parametric scenario

Parametric scenarios are designed to validate tracer and span interfaces. They are more lightweight and support testing features with many input parameters. They should be used to test operations such as creating spans, setting tags, setting links, injecting/extracting http headers, getting tracer configurations, etc. You can find dedicated parametric instructions in the [parametric.md](https://github.com/DataDog/system-tests/blob/main/docs/scenarios/parametric.md).

### Auto-Inject/OnBoarding/SSI scenarios

Automatic library injection simplifies the APM onboarding experience for customers deploying Java, Node.js, .NET, Python and Ruby applications in VMs and docker environments. Datadog software installed on the machine will be intercept the startup of your application and it will inject the tracer library automatically. The OnBoarding scenarios reproduce different environments and check the library injection is done correctly. The SSI scenario can be splitted in two scenarios:
* AWS SSI tests: Run an AWS EC2 instance and install a provision. A provision usually is a Datadog SSI software  installation and a weblog instalation. We check that the weblog is auto instrumented. More detailled documentation can be found [here](onboarding.md).
* Docker SSI tests: Run on docker and install a provision. A provision usually is a Datadog SSI software  installation and a weblog instalation. We check that the weblog is auto instrumented. More detailled documentation can be found [here](docker_ssi.md).

### Kubernetes Auto-Inject/SSI scenarios

The lib-injection project is a feature to allow injection of the Datadog library into a customer's application container without requiring them to modify their application images.

This feature enables applications written in Java, Node.js, Python, .NET or Ruby running in Kubernetes to be automatically instrumented with the corresponding Datadog APM libraries. More detailled documentation can be found [here](https://github.com/DataDog/system-tests/blob/main/docs/scenarios/k8s_lib_injection.md).