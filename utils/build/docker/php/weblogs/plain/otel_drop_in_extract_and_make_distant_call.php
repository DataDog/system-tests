<?php

require_once __DIR__ . "/vendor/autoload.php";

$url = $_GET["url"] ?? null;
if ($url === null) {
    http_response_code(400);
    header("Content-Type: application/json");
    echo json_encode(["error" => "url parameter required"]);
    exit();
}

// Collect incoming headers (lowercase keys) for OTel propagator extraction.
// In restart extract mode, the DD drop-in creates a new root context with
// span links to the incoming trace, rather than propagating it directly.
$headers = [];
foreach (getallheaders() as $k => $v) {
    $headers[strtolower($k)] = $v;
}

$context = \OpenTelemetry\API\Globals::propagator()->extract($headers);

$tracer = \OpenTelemetry\API\Globals::tracerProvider()->getTracer('dd-trace-php/system-tests');
$span = $tracer->spanBuilder('otel_extract_distant_call')
    ->setParent($context)
    ->setSpanKind(\OpenTelemetry\API\Trace\SpanKind::KIND_SERVER)
    ->startSpan();
$scope = $span->activate();

// Make the distant call; auto-instrumentation propagates the active span context.
$ch = curl_init($url);
$response_headers = [];
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HEADER, false);
curl_setopt($ch, CURLINFO_HEADER_OUT, true);
curl_setopt($ch, CURLOPT_HEADERFUNCTION, function ($curl, $header) use (
    &$response_headers,
) {
    $len = strlen($header);
    $parts = explode(":", $header, 2);
    if (count($parts) === 2) {
        $response_headers[strtolower(trim($parts[0]))] = trim($parts[1]);
    }
    return $len;
});
$status_code = 0;
$request_headers = [];
try {
    curl_exec($ch);
    $status_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $raw = curl_getinfo($ch, CURLINFO_HEADER_OUT);
    if ($raw) {
        foreach (explode("\r\n", $raw) as $line) {
            if (strpos($line, ":") !== false) {
                [$k, $v] = explode(":", $line, 2);
                $request_headers[strtolower(trim($k))] = trim($v);
            }
        }
    }
    curl_close($ch);
    $span->end();
} finally {
    $scope->detach();
}

header("Content-Type: application/json");
echo json_encode([
    "url" => $url,
    "status_code" => $status_code,
    "request_headers" => $request_headers,
    "response_headers" => $response_headers,
]);
