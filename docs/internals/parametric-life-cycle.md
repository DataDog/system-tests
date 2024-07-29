Parametric scenario is a scenario that only targets libraries. It spawns, for each test, docker network, a container with the tested library behind a custom HTTP interface\*, and a container with a test agent. Those three items are removed at the end of the test.

To keep this scenario reasonably fast, it also use `xdist` plugin, that split the test session in as many core as it exists. Here is an example with two cores :

![Output on success](../../utils/assets/parametric_infra.png?raw=true)

Note : [previously a gRPC interface](https://github.com/DataDog/system-tests/issues/1930)
