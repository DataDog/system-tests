# Flushing

## Default behavior

Before running assertions, the system-test will wait a certain amount of time (defined in [\_scenarios.py](https://github.com/DataDog/system-tests/blob/9ae1dcff8ca55bcc4157781a406bbcafeb358d54/utils/_context/_scenarios.py#L424)), to wait for all remaining data to be flushed.
It will then stop the weblog container, and only then run all the assertions.

## Implicit flushing

Before running the assertions, the system-tests will stop the weblog application. If your library supports reliably flushing all data at shutdown time, you may use that mecanism to reduce the default delay to 0, and instead rely on that shutdown event. Please make sure your implementation is not flaky, before making that modification.

## Explicit flushing

It is possible to use explicit flushing instead of the default delay.
To do so, implement an endpoint in your weblog `GET /flush`, that when called, will force the flushing of all library data.
You then need to add your library to the list of supported explicity flushing in: TODO LINK, and finally you can set your library delay to 0.
