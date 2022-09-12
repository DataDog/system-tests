
## Description

Build images used for system tests.


## Usage

```bash
    ./build.sh <library_name> [--images <image_names>] [--weblog-variant <variant_name>]
```

## Options

* `<library_name>`: library to test. See LIBRARIES section.
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
* For `golang`: `net-http` (default), `gorilla`
* For `java`: `spring-boot` (default)
* For `nodejs`: `express4` (default), `express4-typescript`
* For `php`: `apache-mod-8.1`, `apache-mod-8.0` (default), `apache-mod-7.4`, `apache-mod-7.3`, `apache-mod-7.2`, `apache-mod-7.1`, `apache-mod-7.0`, `apache-mod-8.1-zts`, `apache-mod-8.0-zts`, `apache-mod-7.4-zts`, `apache-mod-7.3-zts`, `apache-mod-7.2-zts`, `apache-mod-7.1-zts`, `apache-mod-7.0-zts`, `php-fpm-8.1`, `php-fpm-8.0`, `php-fpm-7.4`, `php-fpm-7.3`, `php-fpm-7.2`, `php-fpm-7.1`, `php-fpm-7.0`
* For `python`: `flask-poc` (default), `uwsgi-poc`, `django-poc`
* For `ruby`: `rails70` (default), `rack`, `sinatra21`, and lot of other sinatra/rails versions


## Real life examples

By default, all images will uses production version of components (library and agent). You can use a specific
version of a component by adding it inside `binaries/` ([documentation](binaries.md)). The main idea behind this behavior is to test a specific
version **against** production version of other components.

## Environement variables

You can define your setup in environment variable in a `.env` file. Here is the mapping: 

* `<library_name>` => `TEST_LIBRARY`
* `-i`/`--images` => `BUILD_IMAGES`
* `-w`/`--weblog-variant` => `WEBLOG_VARIANT`
