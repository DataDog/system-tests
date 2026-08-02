<?php

$decision = $_GET["decision"] ?? '';
if ($decision !== 'keep' && $decision !== 'drop') {
    http_response_code(400);
    header('Content-Type: text/plain');
    echo 'decision must be keep or drop';
    exit;
}

// set_priority_sampling is what \DDTrace\Span::setTag does for the manual.keep / manual.drop tags,
// and unlike writing the tag into the root span's meta it also overrides a decision propagated upstream.
\DDTrace\set_priority_sampling(
    $decision === 'keep' ? DD_TRACE_PRIORITY_SAMPLING_USER_KEEP : DD_TRACE_PRIORITY_SAMPLING_USER_REJECT
);

// Call downstream so that tests can assert on the sampling decision that gets propagated
$url = 'http://localhost:7777/';
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
