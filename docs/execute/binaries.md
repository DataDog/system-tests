By default, system tests will build a [weblog](../edit/weblog.md) image that ships the latest production version of the specified tracer language library.

But we often want to run system tests against unmerged changes. The general approach is to identify the git commit hash that contains your changes and use this commit has to download a targeted build of the tracer. Note: ensure that the commit has been pushed to a remote branch first, and when taking the commit hash, ensure it is the full hash. You can identify the commit hash using `git log` or from the github UI.


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

For "regular" system tests (weblog), create a file `golang-load-from-go-get` under the `binaries` directory that specifies the target build. The content of this file will be installed by the weblog via `go get`. Content example:
    * `gopkg.in/DataDog/dd-trace-go.v1@main` Test the main branch
    * `gopkg.in/DataDog/dd-trace-go.v1@v1.67.0` Test the 1.67.0 release
    * `gopkg.in/DataDog/dd-trace-go.v1@<commit_hash>` Test un-merged changes

For parametric tests, run the following commands inside of the system-tests/utils/build/docker/golang/parametric directory:

```sh
go get -u gopkg.in/DataDog/dd-trace-go.v1@<commit_hash>
go mod tidy
```

* Content example:
    * `gopkg.in/DataDog/dd-trace-go.v1@main` Test the main branch
    * `gopkg.in/DataDog/dd-trace-go.v1@v1.67.0` Test the 1.67.0 release


## Java library

Follow these steps to run Parametric tests with a custom Java Tracer version:

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

4. Run Parametric tests from the `system-tests/parametric` folder:

```bash
TEST_LIBRARY=java ./run.sh test_span_sampling.py::test_single_rule_match_span_sampling_sss001
```

## NodeJS library

1. Create a file `nodejs-load-from-npm` in `binaries/`, the content will be installed by `npm install`. Content example:
    * `DataDog/dd-trace-js#master`
2. Clone the dd-trace-js repo inside `binaries`
3. Create a file `nodejs-load-from-local` in `binaries/`, this will disable installing with `npm install dd-trace` and
   will instead get the content of the file, and use it as a location of the `dd-trace-js` repo and then mount it as a
   volume and `npm link` to it. For instance, if this repo is at the location, you can set the content of this file to
   `../dd-trace-js`. This also removes the need to rebuild the weblog image since the code is mounted at runtime.

## PHP library

- Place `datadog-setup.php` and `dd-library-php-[X.Y.Z+commitsha]-aarch64-linux-gnu.tar.gz` (or the `x86_64` if you're not on ARM) in `/binaries` folder
  - You can download those from the `build_packages/package extension` job artifacts, from a CI run of your branch.
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

* Create an file `ruby-load-from-bundle-add` in `binaries/`, the content will be installed by `bundle add`. Content example:
  * `gem 'datadog', git: "https://github.com/Datadog/dd-trace-rb", branch: "master", require: 'datadog/auto_instrument'`
2. Clone the dd-trace-rb repo inside `binaries`

## WAF rule set

* copy a file `waf_rule_set` in `binaries/`

#### After Testing with a Custom Tracer:
Most of the ways to run system-tests with a custom tracer version involve modifying the binaries directory. Modifying the binaries will alter the tracer version used across your local computer. Once you're done testing with the custom tracer, ensure you **remove** it. For example for Python:
```bash
rm -rf binaries/python-load-from-pip
```

----

Hint for components who allows to have the repo in `binaries`, use the command `mount --bind src dst` to mount your local repo => any build of system tests will uses it.
