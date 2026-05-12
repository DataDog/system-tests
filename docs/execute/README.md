## Run tests

You will need a bash based terminal, python3.12, git and docker. Clone this folder, then:

```bash
./build.sh   # build all images
./run.sh     # run tests
```

By default, test will be executed on the Node.js library. Please have a look on [build.sh CLI's documentation](./build.md) for more options.

`./run.sh` has [some options](./run.md), but for now, you won't need them.

## Understanding results

The summary in stdout contains a list of test, then a list of validations. Each test/validations is represented by a letter. Letters can be (see [glossary](../glossary.md) for terminology):

* A green dot: test passed (enabled and successful)
* A small green `x`: xfail - test is disabled and unsuccessful (expected behavior)
* A capital yellow `X`: xpass (easy win) - test is disabled but successful => **it's time to enable the test**
* A capital red `F`: test failed (enabled but unsuccessful) - a more complete explanation will follow
* A small yellow `s`: skipped - test not executed (irrelevant or flaky tests)
* A small red `x`: should not happen, send a message to `#apm-shared-testing` slack channel

If system tests fails, you'll need to dig into logs. Most of the time and with some experience, standard ouput will contains enough info to understand the issue. But sometimes, you'll need to have a look [inside logs/ folder](./logs.md).

## Troubleshooting

For troubleshooting check the troubleshooting [page](./troubleshooting.md).

---

## In this section

- [Build](./build.md) -- build options, weblog variants, image names
- [Run](./run.md) -- run options, test selection, scenarios, sleep mode
- [Test outcomes](./test-outcomes.md) -- detailed explanation of test result states
- [Logs](./logs.md) -- log folder structure and what each file contains
- [Replay mode](./replay.md) -- re-run tests without rebuilding the environment
- [Custom tracer versions](./binaries.md) -- testing with local or unmerged tracer builds
- [Troubleshooting](./troubleshooting.md) -- common issues, debugging tips, and tracer debug output

## See also

- [Scenarios](../understand/scenarios/README.md) -- understand the different scenario types
- [Writing tests](../edit/README.md) -- how to add or modify tests
- [Architecture overview](../understand/architecture.md) -- how the test components work together
- [Back to documentation index](../README.md)
