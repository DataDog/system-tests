<?php

$dbPath = getenv('SYMFONY_DB_PATH') ?: '/tmp/symfony.db';
$db = new PDO("sqlite:$dbPath");
$db->exec('CREATE TABLE IF NOT EXISTS users (id VARCHAR(255) PRIMARY KEY, username VARCHAR(255) UNIQUE NOT NULL, password VARCHAR(255) NOT NULL, name VARCHAR(255))');

$hash1 = password_hash('1234', PASSWORD_BCRYPT);
$db->exec("INSERT OR IGNORE INTO users (id, username, password, name) VALUES ('social-security-id', 'test', '$hash1', 'test')");

$hash2 = password_hash('1234', PASSWORD_BCRYPT);
$db->exec("INSERT OR IGNORE INTO users (id, username, password, name) VALUES ('591dc126-8431-4d0f-9509-b23318d3dce4', 'testuuid', '$hash2', 'testuuid')");

echo "Database initialized at $dbPath\n";
