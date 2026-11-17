# Docker SSI testing

## Quick start

Docker SSI is the fastest way to test library injection. If you are new to
SSI, start here.

Check the [common requirements](../../execute/ssi-access.md#common-requirements).
Most test cases need no other access.

Run the wizard from the repository root:

```bash
./utils/scripts/ssi_wizards/docker_ssi_wizard.sh
```

The wizard selects a valid test case and prints the final command.

- [Choose another SSI test suite](../../execute/ssi.md)
- [Run Docker SSI manually](#run-the-scenario)

## Contents

1. [Overall](#Overall)
2. [Run the tests](#Run-the-tests)
   * [Prerequisites](#Prerequisites)
     - [System-tests requirements](#System-tests-requirements)
   * [Run the scenario](#run-the-scenario)
3. [How to develop tests](#How-to-develop-a-test-case)
   * [Folders and Files structure](#Folders-and-Files-structure)
   * [How the images are built](#how-the-images-are-built)
   * [Docker SSI definitions](#Docker-SSI-definitions)
   * [Create a new weblog](#Create-a-new-weblog)
     - [Create a new weblog using a prebuilt docker image](#Create-a-new-weblog-using-a-prebuilt-docker-image)
     - [Create a new weblog deployable on different containers or operating systems](#Create-a-new-weblog-deployable-on-different-containers-or-operating-systems)
   * [Create a new test case](#Create-a-new-test-case)

# Overall

The Docker SSI tests are an easy and fast tests to check the SSI instrumentation.
The Docker SSI tests don't pretend to replace the current AWS tests, they only try to complement them, providing a quick checks and verification for some features included in the SSI.

The main differences between the AWS/Onboarding tests and the Docker SSI tests are:

* In Docker SSI, the SSI is installed inside a docker container, instead of using virtual machines.
* The AWS/Onboarding tests better represent real customer scenarios, while Docker SSI does not.
* Docker SSI relies on APM Test Agent, instead of relying on the Datadog's production backend.

The main Docker SSI properties are:

* Install the SSI host injection on the docker container that runs the weblog application.
* Uses APM Test Agent to make the assertions.
* The weblog applications are containerized applications.
* The weblog application container is built by the system-tests scenarios in separate steps.
* The base image of the weblog application container should be parametrizable (detailed in the next sections)

The Docker SSI are good for:

* Test the instrumentation against different runtime versions.
* Test the guardrail features (unsupported versions of the language).
* Test the service naming features on SSI.
* Test the crash tracking features.
* Test other features like profiling, asm...

# Run the tests

## Prerequisites

You need Docker.

Most base images are public. Skip the private registry for those images.

`websphere-app` and `jboss-app` use a private image. Both run in `DOCKER_SSI_SERVICENAMING`. Log in to the private registry before that run. The wizard can do the login.

### System-tests requirements

Set up system-tests first. See the [quick start](../../../README.md#quick-start).

The wizard can install the Python tools for you. It runs `./build.sh -i runner`. Say yes the first time you run it.

## Run the scenario

Run the wizard:

```bash
./utils/scripts/ssi_wizards/docker_ssi_wizard.sh
```

The wizard asks you to:

1. Load the system-tests requirements.
2. Skip the private registry for a public image. Log in for `websphere-app` or `jboss-app`.
3. Choose a language.
4. Choose a scenario, a weblog, and a base image.
5. Choose a runtime, when the weblog needs one.
6. Choose `prod` or `dev`. `prod` uses released components. `dev` uses snapshots.
7. Set a custom tracer or injector image, or skip it.
8. Confirm the command. The wizard runs it only after you type `y`.

This command comes from a real wizard run. It uses Java, the `DOCKER_SSI` scenario, and the jetty weblog:

```bash
./run.sh DOCKER_SSI \
  --ssi-weblog jetty-app \
  --ssi-library java \
  --ssi-base-image public.ecr.aws/lts/ubuntu:22.04 \
  --ssi-arch linux/amd64 \
  --ssi-env prod \
  --ssi-installable-runtime 27.0.1.0+9-zulu
```

Your lists will differ. Run the command the wizard prints.

`--ssi-env` defaults to `prod` when you omit it.

# How to develop tests

## Folders and Files structure

To develop a new test case in the Docker SSI Library injection tests, you need to know about the project folder structure.
The following picture shows the main directories for the Docker SSI tests:

![Folder structure](../images/docker_ssi_lib_injections_folders.png "Folder structure")

* **tests/docker_ssi:** All tests cases are stored on this folder.
* **utils/_context/scenarios/**: In this folder you can find the Docker SSI Lib injection scenario definition.
* **utils/build/ssi/base/:** The base templates for the Docker SSI images, and the base utilities used to build the images, for example the language runtime installers.
* **utils/build/ssi/[lang]/:** The weblog applications docker definitios.
* **utils/scripts/ssi_wizards/docker_ssi_wizard.sh:** Wizard that runs one Docker SSI scenario.
* **utils/docker_ssi:** The core implementation of this test framework.

## How the images are built

The scenario builds the weblog image in four layers. The two lower layers (OS dependencies, language
runtime and Datadog installer) are the base image. CI stores it in the private registry and reuses it.
When you change a file under `utils/build/ssi/base/`, CI builds a new base image on its own.

Locally, Docker reuses cached build steps. Add `--ssi-force-build` after you change something, or to get
the latest SSI version.

For the details, see [Docker SSI images](../../internals/docker-ssi-images.md).

## Docker SSI definitions

Three files define what the Docker SSI tests run:

| File | What it defines |
|------|-----------------|
| `utils/docker_ssi/docker_ssi_images.json` | The base images. Each image has a `name`, an `image` reference and an `architecture`. |
| `utils/docker_ssi/docker_ssi_runtimes.json` | The runtime versions that system-tests can install, by language. Each runtime has a `version_id`, for example `JS2422`, and a `version`, for example `24.22`. |
| `utils/scripts/ci_orchestrators/docker_ssi.json` | The scenarios that run each weblog (`scenario_matrix`), and the images and runtimes that each weblog supports (`weblogs_spec`). In `allowed_runtime_versions`, `"*"` means every runtime of the language. |

`utils/docker_ssi/docker_ssi_definitions.py` repeats the runtimes of `docker_ssi_runtimes.json` as Python classes. The scenario uses it to find the `version_id` of a runtime.

### Add a runtime version

1. Add the runtime to `docker_ssi_runtimes.json`, under its language:

   ```json
   {
     "version_id": "JS2422",
     "version": "24.22"
   }
   ```

2. Add the same runtime to `docker_ssi_definitions.py`, in the class of its language. Also add it to the list that `get_all_versions()` returns.
3. If a weblog lists its runtimes by `version_id` in `docker_ssi.json`, add the new `version_id` to that list. A weblog with `"*"` gets the new runtime with no change.

The script `utils/build/ssi/base/<lang>_install_runtimes.sh` installs the runtime, so it must accept the new `version`. For Node.js, `<lang>` is `js`. In CI, the first run builds the base image for the new runtime and pushes it. For an example, see [#8504](https://github.com/DataDog/system-tests/pull/8504), which adds Node.js 24.22 and 25.9 and Python 3.15.2.

### Add a base image

1. Add the image to `docker_ssi_images.json`. Use a unique `name`, and add one entry for each architecture:

   ```json
   {
     "name": "Tomcat_9_arm64",
     "image": "public.ecr.aws/docker/library/tomcat:9",
     "architecture": "linux/arm64"
   }
   ```

2. In `docker_ssi.json`, add the image `name` to the `supported_images` of each weblog that must run on it.

## Create a new weblog

We can differentiate between two types of applications:

- Applications that come already prepared/wrapped with a base image. For example, tomcat or jboss.
- "Normal” applications that we encapsulate in a docker container and that in theory could be executed in more than one base image. For example, my HelloWorld application could run on Ubuntu22, Debian 12, RedHat.... images.

The two previous points will be better understood by following examplesThe previous.

### Create a new weblog using a prebuilt docker image

For example, the Tomcat Java Web Server is distributed by prebuilt docker images. If we want to test the tomcat 9, but we don't need to test Tomcat 9 installed on different Operating Systems, we could use the tomcat prebuilt images.

If we want to test the tomcat 9 image deploying a web application we'd do this:

```yaml
#Build the web app
FROM maven:3.5.3-jdk-8-alpine as build
WORKDIR /app
COPY lib-injection/build/docker/java/enterprise/ ./
RUN mvn clean package

#Deploy/Run the built app on a tomcat 9
FROM tomcat:9
COPY --from=build app/payment-service/target/payment-service*.war /usr/local/tomcat/webapps/
```

We can convert this standard image into "Docker SSI" image. We only need to parametrize the "From" clause, and store the dockerfile as `utils/build/ssi/java/tomcat-app.Dockerfile`:

```yaml
ARG BASE_IMAGE

FROM maven:3.5.3-jdk-8-alpine as build
WORKDIR /app
COPY lib-injection/build/docker/java/enterprise/ ./
RUN mvn clean package

FROM ${BASE_IMAGE}
COPY --from=build app/payment-service/target/payment-service*.war /usr/local/tomcat/webapps/
#This is the endpoint to be used by the tests to make a request to the weblog. If your app it's listenning on "http://localhost:18080" you don't need to use the "WEBLOG_URL"
ENV WEBLOG_URL=http://localhost:8080/payment-service/
ENV DD_INSTRUMENT_SERVICE_WITH_APM=true
```

As final step, register the new weblog in `utils/scripts/ci_orchestrators/docker_ssi.json`, as explained in [Docker SSI definitions](#docker-ssi-definitions):

* Add the weblog to `weblogs_spec`, under its language. A weblog with a prebuilt image has no `allowed_runtime_versions`:

  ```json
  {
    "name": "tomcat-app",
    "supported_images": [{ "name": "Tomcat_9_arm64" }]
  }
  ```

* Add the weblog to the scenarios that must run it, in `scenario_matrix`.
* If its image is new, add it to `utils/docker_ssi/docker_ssi_images.json`.

---

**NOTE:**

When system-tests builds the docker images it is going to install the SSI software inside of the container.

---

To run the tests of this new weblog in the `DOCKER_SSI_SERVICENAMING` scenario:

```bash
./run.sh DOCKER_SSI_SERVICENAMING --ssi-weblog tomcat-app --ssi-library java --ssi-base-image public.ecr.aws/docker/library/tomcat:9 --ssi-arch linux/arm64
```

### Create a new weblog deployable on different containers or operating systems

We will use these types of weblogs to run an application against different operating systems and distinct language runtime versions.

For example, we can define a PHP application that runs on different OS and PHP runtime versions (`utils/build/ssi/php/php-app.Dockerfile`):

```yaml
ARG BASE_IMAGE

FROM ${BASE_IMAGE}
WORKDIR /app

RUN printf "<?php\necho 'hi'; if (function_exists('dd_trace_internal_fn')) dd_trace_internal_fn(\"finalize_telemetry\");\n" > index.php

# Without the sleep, the docker network has issues
CMD ["sh", "-c", "sleep 2; php -S 0.0.0.0:18080"]
```

As final step, register the new weblog in `utils/scripts/ci_orchestrators/docker_ssi.json`, as explained in [Docker SSI definitions](#docker-ssi-definitions). Add it to `weblogs_spec`, with the images and the runtimes it supports:

```json
{
  "name": "php-app",
  "supported_images": [
    { "name": "Ubuntu_22_amd64", "allowed_runtime_versions": ["*"] },
    { "name": "Ubuntu_22_arm64", "allowed_runtime_versions": ["*"] }
  ]
}
```

Then add it to the scenarios that must run it, in `scenario_matrix`.

---

**NOTE:**

When system-tests builds the docker images it is going to install the SSI software inside of the container and the required runtime version.

---

To run the `DOCKER_SSI` tests of this new weblog with PHP 7.0, pass the `version` of the runtime, not its `version_id`:

```bash
./run.sh DOCKER_SSI --ssi-weblog php-app --ssi-library php --ssi-base-image public.ecr.aws/lts/ubuntu:22.04 --ssi-arch linux/amd64 --ssi-installable-runtime 7.0
```

## Create a new test case

The creation of test methods for the “Docker SSI” scenarios does not require anything special, we will do it as it is done for the rest of the system-tests scenarios.
We can make a request to the deployed weblog and make assertions through the "test agent" interface:

```python
@scenarios.docker_ssi
class TestDockerSSIFeatures:
    """Test the ssi in a simulated host injection environment (docker container + test agent)
    We test that the injection is performed and traces and telemetry are generated.
    If the language version is not supported, we only check that we don't break the app and telemetry is generated."""


    def setup_install_supported_runtime(self):

       parsed_url = urlparse(context.scenario.weblog_url)
       logger.info(f"Setting up Docker SSI installation WEBLOG_URL {context.scenario.weblog_url}")
       self.r = weblog.request(
                "GET", parsed_url.path, domain=parsed_url.hostname, port=parsed_url.port
       )
       logger.info(f"Setup Docker SSI installation {TestDockerSSIFeatures._r}")


    def setup_install_supported_runtime(self):
        self._setup_all()

    @features.ssi_guardrails
    def test_install_supported_runtime(self):
        logger.info(f"Testing Docker SSI installation on supported lang runtime: {context.scenario.library.name}")
        assert self.r.status_code == 200, f"Failed to get response from {context.scenario.weblog_url}"

        # If the language version is supported there are traces related with the request
        traces_for_request = interfaces.test_agent.get_traces(request=self.r)
        assert traces_for_request, f"No traces found for request {self.r.get_rid()}"
        assert "runtime-id" in traces_for_request["meta"], "No runtime-id found in traces"

        # There is telemetry data related with the runtime-id
        telemetry_data = interfaces.test_agent.get_telemetry_for_runtime(traces_for_request["meta"]["runtime-id"])
        assert telemetry_data, "No telemetry data found"

```

You could use the system-tests decorator to skip the tests or mark them as bug. For example:

```python
    @bug(condition=context.library == "python", reason="INPLAT-11")
    @irrelevant(context.library == "java" and context.installed_language_runtime < "1.8.0_0")
    @irrelevant(context.library == "php" and context.installed_language_runtime < "7.0")
    @irrelevant(context.library == "nodejs" and context.installed_language_runtime < "17.0")
    def test_install_supported_runtime(self):
```

