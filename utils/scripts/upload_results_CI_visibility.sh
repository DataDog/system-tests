if test -f ".env"; then
    source .env
fi

export DD_ENV='ci-system-tests-draft3'
export DD_CIVISIBILITY_LOGS_ENABLED='1'
export DD_CIVISIBILITY_AGENTLESS_ENABLED='1'
export DD_SITE=datad0g.com

#Download tool
curl -L --fail "https://github.com/DataDog/datadog-ci/releases/latest/download/datadog-ci_linux-x64" --output "$(pwd)/datadog-ci" && chmod +x $(pwd)/datadog-ci
ls -la
./datadog-ci junit upload --service ci-system-test-service-draft3 $(pwd)/logs/reportJunit.xml 
#logs_uds
#logs_sampling_rate
#logs_missing_appsec_rules
#logs_corrupted_appsec_rules
#logs_custom_appsec_rules
#logs_rules_monitoring_with_errors
#logs_profiling
#logs_appsec_unsupported
#logs_cgroup
#logs_appsec_disabled
#logs_low_waf_timeout
#logs_appsec_custom_obfuscation
#logs_appsec_rate_limiter
#logs_library_conf_custom_headers_short
#logs_library_conf_custom_headers_long
#logs_backend_waf
#logs_remote_config_mocked_backend_features
#logs_remote_config_mocked_backend_live_debugging
#logs_remote_config_mocked_backend_asm_dd
#logs_remote_config_mocked_backend_features_nocache
#logs_remote_config_mocked_backend_live_debugging_nocache
#logs_remote_config_mocked_backend_asm_dd_nocache
#logs_trace_propagation_style_w3c

