param
(
)

# FIXME: have to ignore the root conftest as it does a bunch of initialization/teardown
#        not required for the integration/shared tests.
$env:PARENT_DIR = [System.IO.Path]::GetDirectoryName($pwd)
python -m pytest -n 4 -c $PWD/conftest.py $ARGS