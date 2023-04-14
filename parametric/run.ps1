param
(
)

# FIXME: have to ignore the root conftest as it does a bunch of initialization/teardown
#        not required for the integration/shared tests.
$env:PARENT_DIR = [System.IO.Path]::GetDirectoryName($pwd)
$n = $env:PYTEST_N ?? "auto";

# TODO: support splits/group when fixed
python -m pytest -n $n -c $PWD/conftest.py $ARGS