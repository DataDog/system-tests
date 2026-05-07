<?php

require_once __DIR__ . '/vendor/autoload.php';

// OTel SDK is only available for PHP 8.1+
if (!interface_exists('\\OpenTelemetry\\API\\Trace\\TracerProviderInterface')) {
    http_response_code(501);
    echo 'OTel SDK not available';
    exit;
}

use OpenTelemetry\SDK\Trace\TracerProvider;
use OpenTelemetry\API\Trace\SpanKind;
use OpenTelemetry\API\Trace\StatusCode;

$parentName = $_GET['parentName'] ?? 'parent-span';
$childName  = $_GET['childName']  ?? 'child-span';
$shouldIndex = ($_GET['shouldIndex'] ?? '0') === '1';

$tracerProvider = new TracerProvider();
$tracer = $tracerProvider->getTracer('system-tests');

// Parent span — use setParent(false) so Context::resolve() returns getRoot(),
// detaching from the active HTTP request span and making this a true root span.
$parentSpan = $tracer->spanBuilder($parentName)
    ->setParent(false)
    ->setSpanKind(SpanKind::KIND_INTERNAL)
    ->startSpan();
$parentScope = $parentSpan->activate();

if ($shouldIndex) {
    $parentSpan->setAttribute('_dd.filter.kept', 1);
    $parentSpan->setAttribute('_dd.filter.id', 'system_tests_e2e');
}
$parentSpan->setAttribute('attributes', 'values');
$parentSpan->setAttribute('language', 'php');
// Propagate user-agent for request correlation
$parentSpan->setAttribute('http.useragent', $_SERVER['HTTP_USER_AGENT'] ?? '');

// Signal error via status (maps to error.message on the DDTrace span)
$parentSpan->setStatus(StatusCode::STATUS_ERROR, 'testing_end_span_options');

// Child span: duration ~1 second, kind = Internal
$startNs = (int)(microtime(true) * 1e9);
$childSpan = $tracer->spanBuilder($childName)
    ->setSpanKind(SpanKind::KIND_INTERNAL)
    ->setStartTimestamp($startNs)
    ->startSpan();
$childScope = $childSpan->activate();

if ($shouldIndex) {
    $childSpan->setAttribute('_dd.filter.kept', 1);
    $childSpan->setAttribute('_dd.filter.id', 'system_tests_e2e');
}
$childSpan->setAttribute('http.useragent', $_SERVER['HTTP_USER_AGENT'] ?? '');

$childSpan->end($startNs + 1_000_000_000); // 1 second duration
$childScope->detach();

$parentSpan->end();
$parentScope->detach();

$tracerProvider->shutdown();

echo 'OK';
