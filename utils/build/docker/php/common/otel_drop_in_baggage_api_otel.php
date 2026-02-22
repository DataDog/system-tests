<?php

use OpenTelemetry\API\Baggage\Baggage;

// Get query parameters
$url = $_GET['url'] ?? null;
$baggage_remove = $_GET['baggage_remove'] ?? null;
$baggage_set = $_GET['baggage_set'] ?? null;

if ($url === null) {
    http_response_code(400);
    echo json_encode(['error' => 'Specify the url to call in the query string']);
    exit;
}

// Get the current baggage using OpenTelemetry API
$baggage = Baggage::getCurrent();
$builder = $baggage->toBuilder();

// Remove baggage items using OTel builder
if ($baggage_remove !== null) {
    $items_to_remove = explode(',', $baggage_remove);
    foreach ($items_to_remove as $key) {
        $builder = $builder->remove(trim($key));
    }
}

// Set baggage items using OTel builder
if ($baggage_set !== null) {
    $items_to_set = explode(',', $baggage_set);
    foreach ($items_to_set as $item) {
        $parts = explode('=', $item, 2);
        if (count($parts) === 2) {
            $builder = $builder->set(trim($parts[0]), trim($parts[1]));
        }
    }
}

// Build the new baggage and activate it
$newBaggage = $builder->build();
$scope = $newBaggage->activate();

try {
    // Make the HTTP request with curl - tracer will auto-propagate baggage
    $ch = curl_init($url);

    // Configure curl to capture request and response headers
    $request_headers_array = [];
    $response_headers_array = [];

    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HEADER, false);

    // Capture request headers
    curl_setopt($ch, CURLINFO_HEADER_OUT, true);

    // Capture response headers
    curl_setopt($ch, CURLOPT_HEADERFUNCTION, function($curl, $header) use (&$response_headers_array) {
        $len = strlen($header);
        $header = explode(':', $header, 2);
        if (count($header) < 2) {
            return $len;
        }
        $name = strtolower(trim($header[0]));
        $value = trim($header[1]);
        $response_headers_array[$name] = $value;
        return $len;
    });

    // Execute the request
    $response_body = curl_exec($ch);
    $status_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);

    // Get request headers
    $request_headers_raw = curl_getinfo($ch, CURLINFO_HEADER_OUT);
    if ($request_headers_raw) {
        $request_headers_lines = explode("\r\n", $request_headers_raw);
        foreach ($request_headers_lines as $line) {
            if (strpos($line, ':') !== false) {
                list($key, $value) = explode(':', $line, 2);
                $request_headers_array[trim($key)] = trim($value);
            }
        }
    }

    curl_close($ch);

    // Return the response
    $result = [
        'url' => $url,
        'status_code' => $status_code,
        'request_headers' => $request_headers_array,
        'response_headers' => $response_headers_array
    ];

    header('Content-Type: application/json');
    echo json_encode($result);
} finally {
    $scope->detach();
}
