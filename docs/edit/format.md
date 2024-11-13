System tests code is in python, and is linted/formated using [black](https://black.readthedocs.io/en/stable/) and [pylint](https://pylint.readthedocs.io/en/latest/).

The only pre-req is: [python3.12](https://www.python.org/downloads/).
Then, run the linter with:

```bash
./format.sh
```

Any library app code (that is, code written in Java, Golang, .NET, etc in weblog or parametric apps) will need to be formatted using that library's formatter.
