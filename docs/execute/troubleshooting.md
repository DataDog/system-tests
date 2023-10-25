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
