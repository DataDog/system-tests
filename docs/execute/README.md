

## Run tests

You will only need `docker-compose`. Clone this folder, and at root level, create a `.env` file with `DD_API_KEY=<a_valid_staging_api_key>`. Then: 

```bash
./build.sh   # build all images
./run.sh     # run tests
```

By default, test will be executed on the nodeJS library. Please have a look on [build.sh CLI's documentation](./build.md) for more options.

`./run.sh` has [some options](./run.md), but for now, you won't need them.

## Understanding results

If system tests fails, you'll need to dig into logs. Most of the time and with some experience, standard ouput will contains enough info to understand the issue. But sometimes, you'll need to have a look [inside logs/ folder](./logs.md).