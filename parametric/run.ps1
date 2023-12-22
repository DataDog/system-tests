param
(
)

# FIXME: have to ignore the root conftest as it does a bunch of initialization/teardown
#        not required for the integration/shared tests.
$env:PARENT_DIR = [System.IO.Path]::GetDirectoryName($pwd)
$DEFAULT_COUNT = "auto"

# FIXME: all languages should be supported
if (![string]::IsNullOrEmpty($env:CLIENTS_ENABLED)) {
    foreach ($client in $env:CLIENTS_ENABLED.split(',')) {
        # default to "1" for languages with concurrency issues
        if ($client -eq "dotnet" ) {
            $DEFAULT_COUNT = "1"
            break
        }
    }
} else {
    # default to "1" for all languages since that includes problematic languages
    $DEFAULT_COUNT = "1"
}

# TODO: default to "auto" when dotnet is fixed
$PYTEST_WORKER_COUNT = $env:PYTEST_WORKER_COUNT ? $env:PYTEST_WORKER_COUNT : $DEFAULT_COUNT

$CMD = "python -m pytest -n $PYTEST_WORKER_COUNT"

# FIXME: dotnet hangs when this plugin is enabled even when both "splits" and
# "group" are set to "1" which should do effectively nothing.
if (![string]::IsNullOrEmpty($env:PYTEST_SPLITS) -and ![string]::IsNullOrEmpty($env:PYTEST_GROUP)) {
    $CMD = "$CMD --splits $env:PYTEST_SPLITS --group $env:PYTEST_GROUP"
}

$CMD = "$CMD -c $PWD/conftest.py $ARGS"

Invoke-Expression $CMD
