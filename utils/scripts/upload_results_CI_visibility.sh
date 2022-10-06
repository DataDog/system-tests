if test -f ".env"; then
    source .env
fi

export DD_ENV='ci-system-tests-draft3'
export DD_CIVISIBILITY_LOGS_ENABLED='1'
export DD_CIVISIBILITY_AGENTLESS_ENABLED='1'

#Download tool
curl -L --fail "https://github.com/DataDog/datadog-ci/releases/latest/download/datadog-ci_linux-x64" --output "$(pwd)/datadog-ci" && chmod +x $(pwd)/datadog-ci

./datadog-ci junit upload --service ci-system-test-service-draft3 $(pwd)/$SYSTEMTESTS_LOG_FOLDER/reportJunit.xml 
