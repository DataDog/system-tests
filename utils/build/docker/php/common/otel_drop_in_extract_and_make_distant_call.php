<?php

require_once __DIR__ . "/vendor/autoload.php";

$url = $_GET["url"] ?? null;
if ($url === null) {
    http_response_code(400);
    header("Content-Type: application/json");
    echo json_encode(["error" => "url parameter required"]);
    exit();
}

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
curl_exec($ch);
$status_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$request_headers = [];
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

header("Content-Type: application/json");
echo json_encode([
    "url" => $url,
    "status_code" => $status_code,
    "request_headers" => $request_headers,
    "response_headers" => $response_headers,
]);
