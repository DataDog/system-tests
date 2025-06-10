<?php

function error(){
	echo "Error parsing uri";
	exit;
}

$uri = explode('/', $_SERVER["REQUEST_URI"]);

if (count($uri) < 4) {
	error();
}


$rootSpan = \DDTrace\root_span();
$rootSpan->meta["http.route"] = '/tag_value/{tag_value}/{status_code}';

$value = $uri[2];
$response_code= strtok($uri[3], '?'); //There can be url parameters. Lets remove them

if (!is_numeric($response_code)) {
	error();
}

//This is done automatically on framework integrations
\datadog\appsec\push_addresses(["server.request.path_params" => [
	'tag_value' => $value,
	'status_code' => $response_code,
]]);

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
