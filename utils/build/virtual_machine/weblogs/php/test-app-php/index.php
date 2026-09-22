<?php

if (getenv('SYSTEM_TESTS_PROFILING_DEBUG') === '1') {
    $profilingDebug = array(
        'pid' => getmypid(),
        'sapi' => PHP_SAPI,
        'profiling_extension_loaded' => extension_loaded('datadog-profiling'),
        'profiling_extension_version' => phpversion('datadog-profiling'),
        'profiling_enabled' => ini_get('datadog.profiling.enabled'),
        'profiling_log_level' => ini_get('datadog.profiling.log_level'),
    );
    error_log('SYSTEM_TESTS_PROFILING_DEBUG ' . json_encode($profilingDebug));
}

echo 'Hello!';
