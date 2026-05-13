<?php

// Get query parameters
$url = $_GET['url'] ?? null;
$baggage_remove = $_GET['baggage_remove'] ?? null;
$baggage_set = $_GET['baggage_set'] ?? null;

if ($url === null) {
    http_response_code(400);
    echo json_encode(['error' => 'Specify the url to call in the query string']);
    exit;
}

// Modify baggage on the current span using DDTrace API
$span = \DDTrace\root_span();
if ($span !== null) {
    // Remove baggage items
    if ($baggage_remove !== null) {
        $items_to_remove = explode(',', $baggage_remove);
        foreach ($items_to_remove as $key) {
            unset($span->baggage[trim($key)]);
        }
    }

    // Set baggage items
    if ($baggage_set !== null) {
        $items_to_set = explode(',', $baggage_set);
        foreach ($items_to_set as $item) {
            $parts = explode('=', $item, 2);
            if (count($parts) === 2) {
                $span->baggage[trim($parts[0])] = trim($parts[1]);
            }
        }
    }
}

// Make the HTTP request with curl - tracer will auto-propagate baggage
$ch = curl_init($url);

$response_headers_array = [];

curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HEADER, false);
curl_setopt($ch, CURLINFO_HEADER_OUT, true);

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

$response_body = curl_exec($ch);
$status_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);

$request_headers_array = [];
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

$result = [
    'url' => $url,
    'status_code' => $status_code,
    'request_headers' => $request_headers_array,
    'response_headers' => $response_headers_array
];

header('Content-Type: application/json');
echo json_encode($result);
