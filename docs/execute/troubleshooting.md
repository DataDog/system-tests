## On Mac/Parametric tests, fix "allow incoming internet connection" popup 

??

## weblog image is not found ?

When running `build.sh`, you have this error : 

```
ERROR: failed to solve: system_tests/weblog: pull access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed
```

It says it try to get `system_tests/weblog` image from docker hub because it does not exists loccaly. But a `docker images ls -a | grep weblog` says this image exists. You may not using the `default` docker buildx, try `docker buildx use default`.
