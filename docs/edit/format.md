System tests code is in python, and is linted/formated using [mypy](https://mypy.readthedocs.io/en/stable/), [black](https://black.readthedocs.io/en/stable/) and [pylint](https://pylint.readthedocs.io/en/latest/).

Ensure you meet the other pre-reqs in [README.md](../../README.md#requirements)
Then, run the linter with:

```bash
./format.sh
```

It also lints the `express` and `fastify` Node.js weblogs, in a Docker container, whose image is pulled from the system-tests mirror when `USE_IMAGE_MIRROR` is enabled. This step is skipped when nothing changed in their folders or in `format.sh` since the merge base with `origin/main`, committed or not. When the changes can't be listed (not a git checkout, shallow clone, or no `origin/main`), it runs. Use `./format.sh --force-nodejs-lint` to always run it.

Any library app code (that is, code written in Java, Golang, .NET, etc in weblog or parametric apps) will need to be formatted using that library's formatter.
