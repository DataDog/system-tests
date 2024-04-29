<?php

function error(){
	echo "Error parsing uri";
	exit;
}

$uri = explode('/', $_SERVER["REQUEST_URI"]);

if (count($uri) < 4) {
	error();
}

$value = $uri[2];
$response_code= strtok($uri[3], '?'); //There can be url parameters. Lets remove them

if (!is_numeric($response_code)) {
	error();
}

\datadog\appsec\track_custom_event('system_tests_appsec_event',
[
    'value' => $value
]);

foreach ($_GET as $key => $value) {
	header(ucwords($key) . ": " . $value);
}

if ($response_code !== 200) {
    http_response_code($response_code);
}

$body = "Value tagged";
$payloadInResponse = 'payload_in_response_body';
if (substr($value, 0, strlen($payloadInResponse)) === $payloadInResponse && $_SERVER['REQUEST_METHOD'] === 'POST') {
	header('content-type: application/json');
	parse_str(file_get_contents('php://input'), $parsedRequest);
	$body = sprintf('{"payload": %s }', json_encode($parsedRequest));
}

echo $body;
