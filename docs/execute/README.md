

## Run tests

You will need a bash based terminal, python3.12, git and docker. Clone this folder, then:

```bash
./build.sh   # build all images
./run.sh     # run tests
```

By default, test will be executed on the Node.js library. Please have a look on [build.sh CLI's documentation](./build.md) for more options.

`./run.sh` has [some options](./run.md), but for now, you won't need them.

## Understanding results

The summary in stdout contains a list of test, then a list of validations. Each test/validations is represented by a letter. Letters can be :

* A green dot: everything is good
* A small green `x`: expected to fail, and indeed, failing
* A capital yellow `X`: it was expected to fail, but was a success => **it's time to activate the test**
* A capital red `F`: Test is failing! a more complete explanation will follow
* A small yellow `s`: totally skipped. For irrelevant or flaky tests, there is no point to execute them
* A small red `x`: should not happen, send a message to `#apm-shared-testing` slack channel

If system tests fails, you'll need to dig into logs. Most of the time and with some experience, standard ouput will contains enough info to understand the issue. But sometimes, you'll need to have a look [inside logs/ folder](./logs.md).

## Troubleshooting

For troubleshooting check the troubleshooting [page](./troubleshooting.md)
