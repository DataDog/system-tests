<?php

$user_id = null;
$contentType = $_SERVER['CONTENT_TYPE'] ?? "";
switch ($contentType) {
	case 'application/json':
		$body = file_get_contents("php://input");
		$decoded = json_decode($body, 1);
		$user_id = $decoded["user_id"];
		break;
	case 'application/xml':
		$body = file_get_contents("php://input");
		$decoded = simplexml_load_string(stripslashes($body));
		$user_id = (string)$decoded[0];
		break;
	default:
		$user_id = $_REQUEST["user_id"] ?? null;
		break;
}

try {
	$pdo = new PDO("mysql:dbname=mysql_dbname;host=mysqldb", "mysqldb", "mysqldb");
	$pdo->query("SELECT * FROM users WHERE id='" . $user_id . "'");
} catch (\Exception $e) {
	// Ignore connection/query errors (e.g. RASP block)
}

echo "Hello, SQLi!";
