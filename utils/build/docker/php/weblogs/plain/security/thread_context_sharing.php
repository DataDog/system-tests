<?php

$path = $_GET["path"];

$span = \DDTrace\active_span();
if ($span === null) {
    http_response_code(500);
    exit;
}

// Warm-up: Apache's prefork MPM can hand this request to a worker that has never run
// PHP before, and the tracer publishes its OTel process context (the OTEL_CTX mapping
// only when the first request initialises it.
usleep(1000 * 1000);

file_put_contents($path, "system-tests thread context sharing");

header('Content-Type: application/json');
echo json_encode([
    'trace_id' => \DDTrace\trace_id(),
    'span_id' => (string) $span->id,
]);
