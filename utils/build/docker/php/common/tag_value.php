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

$params = explode('&', $_SERVER['QUERY_STRING']);

if (is_array($params)) {
    foreach ($params as $param) {
	$header = $param;
	if (strpos($param, '=') !== false) {
		$exploded = explode('=', $param);
		$key = $exploded[0] ?? '';
		$value = $exploded[1] ?? '';
		$header = ucwords($key) .  ": " . $value;
	}
        header($header);
    }
}

if ($response_code !== 200) {
    http_response_code($response_code);
}
echo "Value tagged";