System tests code is in python, and is linted using [black](https://black.readthedocs.io/en/stable/).

As the framework uses `docker`, you may not have the setup to run it, and it can be painful to pass the CI. So here here the easy step to a quick setup:

## Using Docker

There is a script `format.sh` in the root of the repository which will package the right `black` version in a Docker image and will run it:

```bash
# format everything
./format.sh

# format a directory or file
./format.sh tests
```

## Using a virtualenv

* [install python 3.9](https://www.python.org/downloads/). You may have it by default:
* run `python3.9 -m venv venv`.
* run `source venv/bin/activate`
  * Windows user, it'll be `venv\Scripts\activate.bat`
  * Fish users, i'll be `. venv/bin/activate.fish`
* run `pip install -r requirements.txt`

Ok, your setup is ok, now, just run : 

```bash
black .
```

Et voila, all your files are correctly formated :tada:

## Manifest files
### Using Docker
As to the manifest files, it can be tedious to order the files/folders by hand. So here are some easy steps to format them:
### Using a virtualenv

Same steps as before for the setup, now, just run : 

```bash
./format-yaml.sh
```

All your manifests are correctly formated