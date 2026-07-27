<?php

$url = $_GET["url"] ?? '';
if (!$url) {
    http_response_code(400);
    header('Content-Type: application/json');
    echo json_encode(['error' => 'url parameter required']);
    exit;
}

$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HEADER, false);
curl_setopt($ch, CURLINFO_HEADER_OUT, true);

$responseHeaders = [];
curl_setopt($ch, CURLOPT_HEADERFUNCTION, function ($curl, $header) use (&$responseHeaders) {
    $len = strlen($header);
    $parts = explode(':', $header, 2);
    if (count($parts) === 2) {
        $responseHeaders[strtolower(trim($parts[0]))] = trim($parts[1]);
    }
    return $len;
});

curl_exec($ch);
$statusCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

$requestHeaders = [];
$rawRequestHeaders = curl_getinfo($ch, CURLINFO_HEADER_OUT);
if ($rawRequestHeaders) {
    foreach (explode("\r\n", $rawRequestHeaders) as $line) {
        if (strpos($line, ':') !== false) {
            list($key, $value) = explode(':', $line, 2);
            $requestHeaders[strtolower(trim($key))] = trim($value);
        }
    }
}

curl_close($ch);

header('Content-Type: application/json');
echo json_encode([
    'url' => $url,
    'status_code' => $statusCode,
    'request_headers' => $requestHeaders,
    'response_headers' => $responseHeaders,
]);
