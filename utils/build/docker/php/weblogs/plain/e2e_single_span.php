<?php

$parentName  = $_GET['parentName']  ?? 'parent-span';
$childName   = $_GET['childName']   ?? 'child-span';
$shouldIndex = ($_GET['shouldIndex'] ?? '0') === '1';

// Propagate the user agent so the system-test framework can correlate
// this request's spans with the request (see system-tests/utils/interfaces/_core.py).
$userAgent = $_SERVER['HTTP_USER_AGENT'] ?? '';

$indexTags = [];
if ($shouldIndex) {
    $indexTags = ['_dd.filter.kept' => 1, '_dd.filter.id' => 'system_tests_e2e'];
}

// Create a fresh root span (new trace, not a child of the HTTP request span)
$parentSpan = \DDTrace\start_trace_span();
$parentSpan->name = $parentName;
$parentSpan->resource = $parentName;
$parentSpan->meta['http.useragent'] = $userAgent;
foreach ($indexTags as $k => $v) {
    $parentSpan->meta[$k] = (string)$v;
}

// Child span
$childSpan = \DDTrace\start_span();
$childSpan->name = $childName;
$childSpan->resource = $childName;
$childSpan->meta['http.useragent'] = $userAgent;
foreach ($indexTags as $k => $v) {
    $childSpan->meta[$k] = (string)$v;
}

// Close child first (10-second duration to be visible), then parent
\DDTrace\close_span(microtime(true) + 10);
\DDTrace\close_span(microtime(true) + 20);

echo 'OK';
