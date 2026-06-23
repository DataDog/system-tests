<?php

require_once __DIR__ . '/vendor/autoload.php';

$url = $_GET['url'] ?? null;
if ($url === null) {
    http_response_code(400);
    header('Content-Type: application/json');
    echo json_encode(['error' => 'url parameter required']);
    exit;
}

// Build carrier from $_SERVER HTTP_* keys
$carrier = [];
foreach ($_SERVER as $key => $value) {
    if (str_starts_with($key, 'HTTP_')) {
        $carrier[strtolower(str_replace('_', '-', substr($key, 5)))] = $value;
    }
}

// In PHP, DDTrace auto-instrumentation processes incoming headers via request_init_hook
// before userland code runs, so the auto-generated web.request span is already the
// restarted root (with span links) when DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT=restart.
// We activate the OTel-extracted context to ensure incoming baggage (e.g. key1=value1)
// is present in the active OTel context so DDTrace propagates it in the curl call.
$context = OpenTelemetry\API\Globals::propagator()->extract($carrier);
$scope = $context->activate();

try {
    $ch = curl_init($url);
    $response_headers = [];
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HEADER, false);
    curl_setopt($ch, CURLINFO_HEADER_OUT, true);
    curl_setopt($ch, CURLOPT_HEADERFUNCTION, function ($curl, $header) use (&$response_headers) {
        $len = strlen($header);
        $parts = explode(':', $header, 2);
        if (count($parts) === 2) {
            $response_headers[strtolower(trim($parts[0]))] = trim($parts[1]);
        }
        return $len;
    });
    curl_exec($ch);
    $status_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $request_headers = [];
    $raw = curl_getinfo($ch, CURLINFO_HEADER_OUT);
    if ($raw) {
        foreach (explode("\r\n", $raw) as $line) {
            if (strpos($line, ':') !== false) {
                [$k, $v] = explode(':', $line, 2);
                $request_headers[strtolower(trim($k))] = trim($v);
            }
        }
    }
    curl_close($ch);

    header('Content-Type: application/json');
    echo json_encode([
        'url'              => $url,
        'status_code'      => $status_code,
        'request_headers'  => $request_headers,
        'response_headers' => $response_headers,
    ]);
} finally {
    $scope->detach();
}
