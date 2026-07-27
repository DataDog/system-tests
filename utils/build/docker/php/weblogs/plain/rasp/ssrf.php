<?php

$domain = null;
$contentType = $_SERVER['CONTENT_TYPE'] ?? "";
switch ($contentType) {
	case 'application/json':
		$body = file_get_contents("php://input");
		$decoded = json_decode($body, 1);
		$domain = $decoded["domain"];
		break;
	case 'application/xml':
		$body = file_get_contents("php://input");
		$decoded = simplexml_load_string(stripslashes($body));
		$domain = (string)$decoded[0];
		break;
	default:
		$domain = urldecode($_REQUEST["domain"]);
		break;
}

file_get_contents('http://'.$domain);

echo "Hello, SSRF!";
