<?php

$path = $_GET["path"];

$span = \DDTrace\active_span();
if ($span === null) {
    http_response_code(500);
    exit;
}

file_put_contents($path, "system-tests thread context sharing");

header('Content-Type: application/json');
echo json_encode([
    'trace_id' => \DDTrace\trace_id(),
    'span_id' => (string) $span->id,
]);
