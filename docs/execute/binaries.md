By default, system tests will build a [weblog](../edit/weblog.md) image that ships the latest production version of the specified tracer language library.

But we often want to run system tests against unmerged changes. The general approach is to identify the git commit hash that contains your changes and use this commit hash to download a targeted build of the tracer. Note: ensure that the commit is pushed to a remote branch first, and when taking the commit hash, ensure you use the full hash. You can identify the commit hash using `git log` or from the github UI.


## Agent

* Add a file `agent-image` in `binaries/`. The content must be a valid docker image name containing the datadog agent, like `datadog/agent` or `datadog/agent-dev:master-py3`.

## C++ library

* Tracer:
There are two ways for running the C++ library tests with a custom tracer:
1. Create a file `cpp-load-from-git` in `binaries/`. Content examples:
    * `https://github.com/DataDog/dd-trace-cpp@main`
    * `https://github.com/DataDog/dd-trace-cpp@<COMMIT HASH>`
2. Clone the dd-trace-cpp repo inside `binaries`

* Profiling: add a ddprof release tar to the binaries folder. Call the `install_ddprof`.

## .Net library

* Add a file `datadog-dotnet-apm-<VERSION>.tar.gz` in `binaries/`. `<VERSION>` must be a valid version number.
  * One way to get that file is from an Azure pipeline (either a recent one from master if the changes you want to test were merged recently, or the one from your PR if it's open)
<img width="1318" alt="Screenshot 2024-03-04 at 14 13 57" src="https://github.com/DataDog/system-tests/assets/1932410/de78860a-5a48-42a0-98cc-85da5613f645">
<img width="558" alt="Screenshot 2024-03-04 at 14 17 09" src="https://github.com/DataDog/system-tests/assets/1932410/934aa4e2-c8a9-4aea-804b-c222d2e51e93">


## Golang library

Create a file `golang-load-from-go-get` under the `binaries` directory that specifies the target build. The content of this file will be installed by the weblog or parametric app via `go get` when the test image is built.

* Content example:
    * `github.com/DataDog/dd-trace-go/v2@main` Test the main branch
    * `github.com/DataDog/dd-trace-go/v2@v2.0.0` Test the 2.0.0 release
    * `github.com/DataDog/dd-trace-go/v2@<commit_hash>` Test un-merged changes

To change Orchestrion version, create a file `orchestrion-load-from-go-get` under the `binaries` directory that specifies the target build. The content of this file will be installed by the weblog or parametric app via `go get` when the test image is built.
* Content example:
    * `github.com/DataDog/orchestrion@latest` Test the latest release
    * `github.com/DataDog/orchestrion@v1.1.0` Test the 1.1.0 release
    * `github.com/DataDog/orchestrion@<commit_hash>` Test un-merged changes

## Java library

Follow these steps to run tests with a custom Java Tracer version:

To run a custom Tracer version from a local branch:

1. Clone the repo and checkout to the branch you'd like to test:
```bash
git clone git@github.com:DataDog/dd-trace-java.git
cd dd-trace-java
```
By default you will be on the `master` branch, but if you'd like to run system-tests on the changes you made to your local branch, `git checkout` to that branch before proceeding.

2. Build Java Tracer artifacts
```
./gradlew :dd-java-agent:shadowJar :dd-trace-api:jar
```

3. Copy both artifacts into the `system-tests/binaries/` folder:
  * The Java tracer agent artifact `dd-java-agent-*.jar` from `dd-java-agent/build/libs/`
  * Its public API `dd-trace-api-*.jar` from `dd-trace-api/build/libs/` into

Note, you should have only TWO jar files in `system-tests/binaries`. Do NOT copy sources or javadoc jars.

4. Build your selected weblog:

```shell
./build.sh java [--weblog-variant spring-boot]
```

5. Run tests from the `system-tests` folder:

```bash
TEST_LIBRARY=java ./run.sh test_span_sampling.py::test_single_rule_match_span_sampling_sss001
```

To run a custom tracer version from a remote branch:

1. Find your remote branch on Github and navigate to the `ci/circleci: build_lib` test.
2. Open the details of the test in CircleCi and click on the `Artifacts` tab.
3. Download the `libs/dd-java-agent-*-SNAPSHOT.jar` and `libs/dd-trace-api-*-SNAPSHOT.jar` and move them into the `system-tests/binaries/` folder.
4. Follow Step 4 from above to run the Parametric tests.

Follow these steps to run the OpenTelemetry drop-in test with a custom drop-in version:

1. Download the custom version from https://repo1.maven.org/maven2/io/opentelemetry/javaagent/instrumentation/opentelemetry-javaagent-r2dbc-1.0/
2. Copy the downloaded `opentelemetry-javaagent-r2dbc-1.0-{version}.jar` into the `system-tests/binaries/` folder

Then run the OpenTelemetry drop-in test from the repo root folder:

- `./build.sh java`
- `TEST_LIBRARY=java ./run.sh INTEGRATIONS -k Test_Otel_Drop_In`

## Node.js library

There are three ways to run system-tests with a custom node tracer.

1. Using a custom tracer existing in a remote branch.
    - Create a file `nodejs-load-from-npm` in `binaries/`
    - In the file, add the path to the branch of the custom tracer. The content will be installed by npm install.
    - Content Examples:
      - `DataDog/dd-trace-js#master`
      - `DataDog/dd-trace-js#<commit-hash>`
    - Run any scenario normally with `./build.sh nodejs` and `./run.sh` and your remote changes will be in effect
2. Using a custom tracer existing in a local branch.
    - Create a file `nodejs-load-from-local` in `binaries/`
    - In the file, add the relative path to the `dd-trace-js` repo.
    - Content Examples:
      - If the `dd-trace-js` repo is in the same directory as the `system-tests` repo, add `../dd-trace-js` to the file.
    - This method will disable installing with npm install dd-trace and will instead get the content of the file, and use it as a location of the `dd-trace-js` repo and then mount it as a volume and npm link to it. This also removes the need to rebuild the weblog image since the code is mounted at runtime.
3. Cloning a custom tracer in `binaries`
    - Clone the `dd-trace-js` repo inside `binaries`.
    - Checkout the remote branch with the custom tracer in the `dd-trace-js` repo that was just cloned.
    - Run any scenario normally with `./build.sh nodejs` and `./run.sh` and your remote changes will be in effect

## PHP library

- Place `datadog-setup.php` and `dd-library-php-[X.Y.Z+commitsha]-*-linux-gnu.tar.gz` in `/binaries` folder
  - You can download the `.tar.gz` from the `package extension: [arm64, aarch64-unknown-linux-gnu]` (or the `amd64` if you're not on ARM) job artifacts (from the `package-trigger` sub-pipeline), from a CI run of your branch.
  - The `datadog-setup.php` can be copied from the dd-trace-php repository root.
- Copy it in the binaries folder

Then run the tests from the repo root folder:

- `./build.sh -i runner`
- `TEST_LIBRARY=php ./run.sh PARAMETRIC` or `TEST_LIBRARY=php ./run.sh PARAMETRIC -k <my_test>`

> :warning: **If you are seeing DNS resolution issues when running the tests locally**, add the following config to the Docker daemon:

```json
  "dns-opts": [
    "single-request"
  ],
```

## Python library

1. Add a file `binaries/python-load-from-pip`, the content will be installed by pip. Content example:
  * `ddtrace @ git+https://github.com/DataDog/dd-trace-py.git`
2. Add a `.tar.gz` or a `.whl` file in `binaries`, pip will install it
3. Clone the dd-trace-py repo inside `binaries`

You can also run:
```bash
echo “ddtrace @ git+https://github.com/DataDog/dd-trace-py.git@<name-of-your-branch>” > binaries/python-load-from-pip
```

## Ruby library

You have two ways to run system-tests with a custom Ruby Tracer version:

1. Create `ruby-load-from-bundle-add` in `binaries` directory with the content that should be added to `Gemfile`. Content example:
  * `gem 'datadog', git: 'https://github.com/Datadog/dd-trace-rb', branch: 'master', require: 'datadog/auto_instrument'`. To point to a specific branch, replace `branch: 'master'` with `branch: '<your-branch>'`. If you want to point to a specific commit, delete the `branch: 'master'` entry and replace it with `ref: '<commit-hash>'`.
2. Clone the dd-trace-rb repo inside `binaries` and checkout the branch that you want to test against.

You can also use `utils/scripts/watch.sh` script to sync your local `dd-trace-rb` repo into the `binaries` folder:

```bash
./utils/scripts/watch.sh /path/to/dd-trace-rb
```

## Rust library

You have two ways to run system-tests with a custom Rust Tracer version:

1. Create `rust-load-from-git` in `binaries` directory with the name of the branch or the ref you want to test.
2. Clone the dd-trace-rs repo inside `binaries` and checkout the branch that you want to test against.

*__Note__: You cannot have `rust-load-from-git` and `dd-trace-rs` folder at the same time, else the build will fail with exit code `128`.*

You can also use `utils/scripts/watch.sh` script to sync your local `dd-trace-rs` repo into the `binaries` folder:

```bash
./utils/scripts/watch.sh /path/to/dd-trace-rs
```

## WAF rule set

* copy a file `waf_rule_set` in `binaries/`

#### After Testing with a Custom Tracer:
Most of the ways to run system-tests with a custom tracer version involve modifying the binaries directory. Modifying the binaries will alter the tracer version used across your local computer. Once you're done testing with the custom tracer, ensure you **remove** it. For example for Python:
```bash
rm -rf binaries/python-load-from-pip
```

----

Hint for components who allows to have the repo in `binaries`, use the command `mount --bind src dst` to mount your local repo => any build of system tests will uses it.
