By default, system tests will build a [weblog](../edit/weblog.md) image that ships the production version of all components.

But, obviously, testing validated versions of components is not really interesting, we need to have a way to install a specific version of at least one component. Here is recipes for each components:

## Agent

- Add a file `agent-image` in `binaries/`. The content must be a valid docker image name containing the datadog agent, like `datadog/agent` or `datadog/agent-dev:master-py3`.

## C++ library

- Tracer: TODO
- Profiling: add a ddprof release tar to the binaries folder. Call the `install_ddprof`.

## .Net library

- Add a file `datadog-dotnet-apm-<VERSION>.tar.gz` in `binaries/`. `<VERSION>` must be a valid version number.
  - One way to get that file is from an Azure pipeline (either a recent one from master if the changes you want to test were merged recently, or the one from your PR if it's open)
    <img width="1318" alt="Screenshot 2024-03-04 at 14 13 57" src="https://github.com/DataDog/system-tests/assets/1932410/de78860a-5a48-42a0-98cc-85da5613f645">
    <img width="558" alt="Screenshot 2024-03-04 at 14 17 09" src="https://github.com/DataDog/system-tests/assets/1932410/934aa4e2-c8a9-4aea-804b-c222d2e51e93">

## Golang library

1. Add a file `golang-load-from-go-get`, the content will be installed by `go get`. Content example:
   - `gopkg.in/DataDog/dd-trace-go.v1@master`
1. Clone the dd-trace-go repo inside `binaries`

## Java library

1. Add a valid `dd-java-agent-<VERSION>.jar` file in `binaries`. `<VERSION>` must be a valid version number.

## NodeJS library

1. Create a file `nodejs-load-from-npm` in `binaries/`, the content will be installed by `npm install`. Content example:
   - `DataDog/dd-trace-js#master`
1. Clone the dd-trace-js repo inside `binaries`

## PHP library

1. Add a valid `.apk` file in `binaries`.

## Python library

1. Add a file `binaries/python-load-from-pip`, the content will be installed by pip. Content example:

- `ddtrace @ git+https://github.com/DataDog/dd-trace-py.git`

2. Add a `.tar.gz` or a `.whl` file in `binaries`, pip will install it
1. Clone the dd-trace-py repo inside `binaries`

## Ruby library

- Create an file `ruby-load-from-bundle-add` in `binaries/`, the content will be installed by `bundle add`. Content example:
  - `gem 'ddtrace', git: "https://github.com/Datadog/dd-trace-rb", branch: "master", require: 'ddtrace/auto_instrument'`

2. Clone the dd-trace-rb repo inside `binaries`

## WAF rule set

- copy a file `waf_rule_set` in `binaries/`

______________________________________________________________________

Hint for components who allows to have the repo in `binaries`, use the command `mount --bind src dst` to mount your local repo => any build of system tests will uses it.
