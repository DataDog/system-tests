param
(
)

# FIXME: have to ignore the root conftest as it does a bunch of initialization/teardown
#        not required for the integration/shared tests.
$env:PARENT_DIR = [System.IO.Path]::GetDirectoryName($pwd)
$n = $env:PYTEST_N ?? "auto";
$splits = $env:PYTEST_SPLITS ?? 1;
$group = $env:PYTEST_GROUP ?? 1;
python -m pytest -n $n --splits $splits --group $group -c $PWD/conftest.py $ARGS