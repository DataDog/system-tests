# Parametric Testing

* To run parametric tests use the document [parametric scenario](../../docs/understand/scenarios/parametric.md). The scenario runs shared tests against all APM libraries via a common HTTP interface.
* Parametric tests live under `tests/parametric/`. The parametric library server per language is in `utils/build/docker/<lang>/parametric/`.
* The parametric HTTP interface is documented in [parametric weblog HTTP interface](../../docs/understand/weblogs/parametric_weblog.md). Whenever you add, remove or change an endpoint (in the client `utils/docker_fixtures/_test_clients/_test_client_parametric.py`, or in a parametric server under `utils/build/docker/<lang>/parametric/`), update that document in the same change: the code is the source of truth, and `tests/test_the_test/test_parametric_interface_doc.py` checks that every endpoint called by the client is documented.

## Running a subset of tests

Always pass a nodeid (file, class, or specific test) to `run.sh` to avoid running the entire parametric suite. This is the most effective way to reduce run time when iterating on a specific test.

```sh
# Run a single test
TEST_LIBRARY=nodejs ./run.sh PARAMETRIC tests/parametric/test_tracer.py::Test_Tracer::test_tracer_span_top_level_attributes

# Run a whole file
TEST_LIBRARY=nodejs ./run.sh PARAMETRIC tests/parametric/test_tracer.py

# Run with -k filter
TEST_LIBRARY=nodejs ./run.sh PARAMETRIC -k test_tracer_span
```

## Skipping the build when iterating on test code

When iterating on test code without changing the library image, add `--skip-parametric-build` to skip rebuilding the parametric library image on every run (~3–4s saved per invocation):

```sh
TEST_LIBRARY=java ./run.sh PARAMETRIC --skip-parametric-build tests/parametric/test_startup_logs.py::Test_Startup_Logs::test_startup_logs_enabled
```

Only safe when `utils/build/docker/<lang>/parametric/` has not changed. Run without the flag after modifying the Dockerfile or app code.

* Full details: see the "Making parametric runs faster" section in [parametric scenario](../../docs/understand/scenarios/parametric.md).
