<?php

// Adds a span event to the request root span (tests/test_span_events.py, tests/test_v1_payloads.py::Test_V1SpanEvents)
$span = \DDTrace\root_span();
if ($span === null) {
    http_response_code(500);
    echo 'root span not found';
    exit;
}

$span->events[] = new \DDTrace\SpanEvent('span.event', ['string' => 'value', 'int' => 1]);

echo '[Event added]';
