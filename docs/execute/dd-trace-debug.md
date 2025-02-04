End-to-end testing requires to have a setup as close as possible to what would be "real condition". It means that we try to not set any environment variaible that would change the library behavior if it's not what would be typically used by our customers (and if it's not what we want to tests).

In consequence, DD_TRACE_DEBUG is not set. Though, it makes any debugging session hard. You can locally (or temporary in your CI) activate this by using one of those two ways :

## `--force-dd-trace-debug` option

By adding this option to your `./run.sh` script, you will activate debug logs in the weblog :

```bash
./run.sh <SCENARIO> --force-dd-trace-debug
```

## Using `SYSTEM_TESTS_FORCE_DD_TRACE_DEBUG` en var

By setting this env var to `true`, you'll achieve the same effect. A convenient way if you want to always have this locally, is to add it to your `.env` file.

```bash
echo "SYSTEM_TESTS_FORCE_DD_TRACE_DEBUG=true" >> .env
```
