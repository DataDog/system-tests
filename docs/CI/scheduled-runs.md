# Scheduled system-tests CI runs

The all system-tests is run every night in the system-tests repo CI with the last
production version of each tracer. This is done to catch regression in system-tests
itself and let find early bugs that could halt merges on other repositories. However,
it is not sufficient to catch regressions on dd-trace repositories since we only run
tests on the last released version and not on the default branch. To ensure constant
quality control each repository is therefore responsible for running system-tests
on its default branch regularly (if possible for each commit) and monitor the results.

Bellow is breakdown of the default branch runs per repository.

- system-tests: nightly runs in [GitHub CI](https://link.com)
    scenario groups: end-to-end,lib-injection,docker-ssi,go_proxies,integration_frameworks
    scenarios: PARAMETRIC
- dd-trace-py: runs on every new commit on default and on a schedule in [GitHub CI](https://github.com/DataDog/dd-trace-py/actions/workflows/system-tests.yml) ([file](https://github.com/DataDog/dd-trace-py/blob/main/.github/workflows/system-tests.yml))
    scenarios:
        AGENT_SUPPORTING_SPAN_EVENTS
        APPSEC_ATO_SDK
        APPSEC_AUTO_EVENTS_EXTENDED
        APPSEC_BLOCKING
        APPSEC_BLOCKING_FULL_DENYLIST
        APPSEC_CORRUPTED_RULES
        APPSEC_CUSTOM_OBFUSCATION
        APPSEC_CUSTOM_RULES
        APPSEC_DISABLED
        APPSEC_LOW_WAF_TIMEOUT
        APPSEC_MISSING_RULES
        APPSEC_RASP
        APPSEC_RASP_NON_BLOCKING
        APPSEC_RASP_WITHOUT_DOWNSTREAM_BODY_ANALYSIS_USING_MAX
        APPSEC_RASP_WITHOUT_DOWNSTREAM_BODY_ANALYSIS_USING_SAMPLE_RATE
        APPSEC_RATE_LIMITER
        APPSEC_RULES_MONITORING_WITH_ERRORS
        APPSEC_RUNTIME_ACTIVATION
        APPSEC_STANDALONE
        APPSEC_STANDALONE_API_SECURITY
        APPSEC_STANDALONE_RASP
        APPSEC_WAF_TELEMETRY
        CROSSED_TRACING_LIBRARIES
        DEBUGGER_EXCEPTION_REPLAY
        DEBUGGER_EXPRESSION_LANGUAGE
        DEBUGGER_PII_REDACTION
        DEBUGGER_PROBES_SNAPSHOT
        DEBUGGER_PROBES_STATUS
        DEBUGGER_SYMDB
        DEFAULT
        IAST_STANDALONE
        INTEGRATIONS
        PARAMETRIC
        REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD
        REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES
        REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING
        RUNTIME_METRICS_ENABLED
        SAMPLING
        SCA_STANDALONE
        INTEGRATIONS_FRAMEWORKS

    Also runs tests for python_lambda: scenrio group lambda_end_to_end

- dd-trace-go: nightly runs in [GitHub CI](https://github.com/DataDog/dd-trace-go/actions/workflows/system-tests.yml?query=branch%3Amain) ([file](https://github.com/DataDog/dd-trace-go/blob/main/.github/workflows/system-tests.yml))
    Non default workflow
- dd-trace-php: No run on default
- dd-trace-js: runs on every new commit on default and on a schedule in [GitHub CI](https://github.com/DataDog/dd-trace-js/actions/workflows/system-tests.yml?query=branch%3Amaster) ([file](https://github.com/DataDog/dd-trace-js/blob/master/.github/workflows/system-tests.yml))
    scenario: OK
    test optimization push: OK
- dd-trace-rb: runs on every new commit on default and on a schedule in [GitHub CI](https://github.com/DataDog/dd-trace-rb/actions/workflows/system-tests.yml?query=branch%3Amaster) ([file](https://github.com/DataDog/dd-trace-rb/blob/master/.github/workflows/system-tests.yml))
    scenario: OK
    test optimization push: OK
- dd-trace-dotnet: nightly runs in [Azure CI](https://github.com/DataDog/dd-trace-go/actions/workflows/system-tests.yml?query=branch%3Amain) ([file](https://github.com/DataDog/dd-trace-go/blob/main/.github/workflows/system-tests.yml))
- nginx-datadog: runs on every new commit on default and on a schedule in [GitHub CI](https://github.com/DataDog/nginx-datadog/actions/workflows/system-tests.yml) ([file](https://github.com/DataDog/nginx-datadog/blob/master/.github/workflows/system-tests.yml))
- dd-trace-cpp: runs on every new commit on default and on a schedule in [GitHub CI](https://github.com/DataDog/dd-trace-cpp/actions/workflows/main.yml) ([file](https://github.com/DataDog/dd-trace-cpp/blob/7a55843f51eb3e3707bec816b7e0a4f9446b1eb9/.github/workflows/main.yml#L16))
    scenario: OK
- httpd-datadog: No system-tests ???
- dd-trace-java: runs on every new commit on default and on a schedule in [GitHub CI](https://github.com/DataDog/dd-trace-java/actions/workflows/run-system-tests.yaml) ([file](https://github.com/DataDog/dd-trace-java/blob/master/.github/workflows/run-system-tests.yaml))
    scenario: OK
- dd-trace-rs: runs on every new commit on default and on a schedule in [GitHub CI](https://github.com/DataDog/dd-trace-rs/actions/workflows/test.yaml) ([file](https://github.com/DataDog/dd-trace-rs/blob/main/.github/workflows/test.yaml))
    scenario: OK
- datadog-lambda-python: runs on every new commit on default in [GitHub CI](https://github.com/DataDog/datadog-lambda-python/actions/workflows/system_tests.yml) ([file](https://github.com/DataDog/datadog-lambda-python/blob/main/.github/workflows/system_tests.yml))
