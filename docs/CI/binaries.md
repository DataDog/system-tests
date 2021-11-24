By default, system tests will build a [weblog](../edit/weblog.md) image that ships the production version of all components.

But, obviously, testing validated versions of components is not really interesting, we need to have a way to install a specific version of at least one component. Here is recipes for each components:


## Agent

TODO

## C++ library

TODO

## .Net library

* Add a file `datadog-dotnet-apm-<VERSION>.tar.gz` in `binaries/`. `<VERSION>` must be a valid version number.

## Golang library

1. Add a file `golang-load-from-go-get`, the content will be installed by `go get`. Content example:
    * `gopkg.in/DataDog/dd-trace-go.v1@a8c99b56c5bf2545da7e38f4ad97b1da5cfe73b7`
2. Clone the dd-trace-go repo inside `binaries`

## Java library

1. Add a valid `dd-java-agent-<VERSION>.jar` file in `binaries`. `<VERSION>` must be a valid version number.

## NodeJS library

* Create an file `nodejs-load-from-npm` in `binaries/`, the content will be installed by `npm install`. Content example:
    * `DataDog/dd-trace-js#master`

## PHP library

1. Add a valid `.apk` file in `binaries`.

## Python library

1. Add a file `binaries/python-load-from-pip`, the content will be installed by pip. Content example:
  * `ddtrace[appsec-beta] @ git+https://github.com/DataDog/dd-trace-py.git@appsec`
2. Add a `.tar.gz` or a `.whl` file in `binaries`, pip will install it

## Ruby library

* Create an file `ruby-load-from-bundle-add` in `binaries/`, the content will be installed by `bundle add`. Content example:
  * `ddtrace --git "https://github.com/Datadog/dd-trace-rb" --branch "master"`
2. Clone the dd-trace-rb repo inside `binaries`
