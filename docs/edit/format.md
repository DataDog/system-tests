System tests code is in python, and is linted/formated using [black](https://black.readthedocs.io/en/stable/) and [pylint](https://pylint.readthedocs.io/en/latest/).

You'll only need [python3.9](https://www.python.org/downloads/) (you may have it by default) to run them, with a unique command : 

```bash
./format.sh
```

There is a good chance that all your files are correctly formated :tada:. For some use-cases where issues can't be automatically fixed, you'll jave the explanation in the output. And you can run only checks, without modifying any file using the `-c` option.
