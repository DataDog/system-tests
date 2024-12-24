<?php

$file = null;
$contentType = $_SERVER['CONTENT_TYPE'] ?? "";
switch ($contentType) {
	case 'application/json':
		$body = file_get_contents("php://input");
		$decoded = json_decode($body, 1);
		$file = $decoded["file"];
		break;
	case 'application/xml':
		$body = file_get_contents("php://input");
		$decoded = simplexml_load_string(stripslashes($body));
		$file = (string)$decoded[0];
		break;
	default:
		$file = urldecode($_REQUEST["file"]);
		break;
}

file_get_contents($file);

echo "Hello, LFI!";
