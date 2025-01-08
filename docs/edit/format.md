System tests code is in python, and is linted/formated using [mypy](https://mypy.readthedocs.io/en/stable/), [black](https://black.readthedocs.io/en/stable/) and [pylint](https://pylint.readthedocs.io/en/latest/).

Ensure you meet the other pre-reqs in [README.md](../../README.md#requirements)
Then, run the linter with:

```bash
./format.sh
```

Any library app code (that is, code written in Java, Golang, .NET, etc in weblog or parametric apps) will need to be formatted using that library's formatter.
