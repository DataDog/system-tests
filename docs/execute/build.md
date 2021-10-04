
## Description

Build images used for system tests.


## Usage

```bash
    ./build.sh [--library <library_name>] [--images <image_names>] [--weblog-variant <variant_name>]
```

## Options

* `-l`: library to test See LIBRARIES section. Default: `nodejs`
* `--library`: Same as `-l`
* `-i`: Comma separated list of images you need to build. See *Image names* section for possible values. Default: all of them
* `--images`: Same as `-i`
* `-w`: Name of a [weblog](../edit/weblog.md) variation
* `--weblog-variant`: same as `-w`

## Image names

* `weblog`: Web app that ships the library.
* `agent`: Host for datadog agent.
* `runner`: Test runner.

## Libraries names

* `cpp`
* `dotnet`
* `golang`
* `java`
* `nodejs`
* `php`
* `python`
* `ruby`


## Weblog variantions

* For `cpp`: `poc` (default)
* For `dotnet`: `poc` (default)
* For `golang`: `echo-poc` (default), `net-http-poc`
* For `java`: `spring-boot-poc` (default)
* For `nodejs`: `express-poc` (default)
* For `php`: `vanilla-poc` (default)
* For `python`: `flask-poc` (default), `uwsgi-poc`
* For `ruby`: `sinatra-poc` (default)


## Real life examples

By default, all images will uses production version of componenents (library and agent). You can use a specific
version of a component by adding it inside `binaries/` ([documentation](../CI/binaries)). The main idea behind this behavior is to test a specific
version **against** production version of other components.

## Environement variables

You can define your setup in environment variable in a `.env` file. Here is the mapping: 

* `-i`/`--images` => `BUILD_IMAGES`
* `-l`/`--library` => `TEST_LIBRARY`
* `-w`/`--weblog-variant` => `WEBLOG_VARIANT`
