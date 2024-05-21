## `docker.errors.DockerException: Error while fetching server API version: ('Connection aborted.', FileNotFoundError(2, 'No such file or directory'))`

Your docker engine is not started or not ready. start it, and wait.
It also happens when you do not allow the default socket to be used (see Advanced options in docker desktop).

## On Mac/Parametric tests, fix "allow incoming internet connection" popup 

The popup should disappear, don't worry

## Errors on build.sh

When running `build.sh`, you have this error : 

### `failed to solve: system_tests/weblog`

```
ERROR: failed to solve: system_tests/weblog: pull access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed
```

It says it try to get `system_tests/weblog` image from docker hub because it does not exists loccaly. But a `docker images ls -a | grep weblog` says this image exists. You may not using the `default` docker buildx, try : 

```bash
docker buildx use default
```

### `open /Users/<username>/.docker/buildx/current: permission denied`

```
Build weblog
ERROR: open /Users/<username>/.docker/buildx/current: permission denied
Build step failed after 1 attempts
```

File permission on your `.docker` are not the good ones : 

```bash
sudo chown -R $(whoami) ~/.docker
```

## NodeJs weblog experimenting segfaults on Mac/Intel

In docker dashbaord, setting, general, untick `Use Virtualization Framework`. See this [Stack overflow thread](https://stackoverflow.com/questions/76735062/segmentation-fault-in-node-js-application-running-in-docker).