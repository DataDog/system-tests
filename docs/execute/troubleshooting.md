## `docker.errors.DockerException: Error while fetching server API version: ('Connection aborted.', FileNotFoundError(2, 'No such file or directory'))`

Your docker engine is either not started or not ready. Start it, and wait a bit before trying again. This error also happens when you do not allow the default socket to be used (see Advanced options in docker desktop).

## On Mac/Parametric tests, fix "allow incoming internet connection" popup

The popup should disappear, don't worry.

## Errors on build.sh

When running `build.sh`, you have this error:

### `failed to solve: system_tests/weblog`

```
ERROR: failed to solve: system_tests/weblog: pull access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed
```

This error message says that the build script tried to pull the `system_tests/weblog` image from docker hub because it does not exist locally. However, `docker image ls -a | grep weblog` says that this image does exist locally. You may need to switch to the `default` docker buildx. Try:

```bash
docker context use default
```

### `open /Users/<username>/.docker/buildx/current: permission denied`

```
Build weblog
ERROR: open /Users/<username>/.docker/buildx/current: permission denied
Build step failed after 1 attempts
```

Adjust file permissions on your `.docker`:

```bash
sudo chown -R $(whoami) ~/.docker
```

## Node.js weblog experimenting segfaults on Mac/Intel

In the docker dashboard -> settings -> general, untick `Use Virtualization Framework`. See this [Stack overflow thread](https://stackoverflow.com/questions/76735062/segmentation-fault-in-node-js-application-running-in-docker) for more information.

## Parametric scenario: `GRPC recvmsg:Connection reset by peer`

The GRPC interface seems to be less stable. So far, the only solution is to retry.

## Parametric scenario: `Fail to bind port`

Docker seems to occasionally keep a host port open, even after the container is removed. There is the wait-and-retry mechanism, but it may not be enough. So far, the only solution is to retry.

## Install python3.12 on ubuntu

`apt-get install python3.12 python3.12-dev python3.12-venv`

## Unable to start postgres instance

When executing `run.sh`, postgres can fail to start and log:

```
/usr/local/bin/docker-entrypoint.sh: line 177: /docker-entrypoint-initdb.d/init_db.sh: Permission denied
```

This may happen if your `umask` prohibits "other" access to files (for example, it is `027` on Datadog Linux laptops). To fix this, try:

```bash
chmod 755 ./utils/build/docker/postgres-init-db.sh
```

Then, rebuild and rerun.
