<?php

require_once __DIR__ . '/vendor/autoload.php';

// OTel SDK + CachedInstrumentation are only available for PHP 8.1+
if (!class_exists('\\OpenTelemetry\\API\\Instrumentation\\CachedInstrumentation')) {
    http_response_code(501);
    echo 'OTel CachedInstrumentation not available';
    exit;
}

use OpenTelemetry\API\Instrumentation\CachedInstrumentation;
use OpenTelemetry\API\Trace\SpanKind;

// Use a name that already starts with "otel." so mark_integration_loaded reports "otel.*" in telemetry.
// Pass a non-null version string: the C-level mark_integration_loaded check requires IS_STRING (null fails).
// The tracer() hook wraps the returned tracer so spans get component="otel.otel.drop-in-test" (double "otel."
// is fine — the test only checks startsWith("otel.")).
$instrumentation = new CachedInstrumentation('otel.drop-in-test', '1.0.0');
$tracer = $instrumentation->tracer();

$span = $tracer->spanBuilder('otel-drop-in-span')
    ->setSpanKind(SpanKind::KIND_INTERNAL)
    ->startSpan();
$scope = $span->activate();
$span->setAttribute('test', 'otel-drop-in');
$span->end();
$scope->detach();

echo 'OK';
