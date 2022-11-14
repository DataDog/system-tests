param
(
)

# FIXME: have to ignore the root conftest as it does a bunch of initialization/teardown
#        not required for the integration/shared tests.
$env:PARENT_DIR = [System.IO.Path]::GetDirectoryName($pwd)
python -m pytest -c $PWD/conftest.py $ARGS