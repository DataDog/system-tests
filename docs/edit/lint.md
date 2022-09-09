System tests code is in python, and is linted using [black](https://black.readthedocs.io/en/stable/).

As the framework use `docker`, you may not have the setup to run it, and it can be painful to pass the CI. So here here the easy step to a quick setup:

* [install python 3](https://www.python.org/downloads/). You may have it by default:
  * run `python --version`. As long as the version is 3, it's ok
  * you can try with `python3 --version`.
* run `python -m venv venv` (use `python3` if the step above works with it).
* run `source venv/bin/activate`
  * Windows user, it'll be `venv\Scripts\activate.bat`
  * Fish users, i'll be `. venv/bin/activate.fish`
* run `pip install -r requirements.txt`

Ok, your setup is ok, now, just run : 

```bash
black .
```

Et voila, all your files are correctly formated :tada:

