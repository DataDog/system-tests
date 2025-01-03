<?php

$domain = null;
$contentType = $_SERVER['CONTENT_TYPE'] ?? "";
switch ($contentType) {
	case 'application/json':
		$body = file_get_contents("php://input");
		$decoded = json_decode($body, 1);
		$domain = $decoded["domain"];
		break;
	default:
		$domain = urldecode($_REQUEST["domain"]);
		break;
}

file_get_contents($domain);

echo "Hello, SSRF!";
