<?php

$service = $_GET['service'] ?? '';
$operation = $_GET['operation'] ?? '';

function getMysqlConnection(): PDO {
    $pdo = new PDO("mysql:dbname=mysql_dbname;host=mysqldb", "mysqldb", "mysqldb");
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    return $pdo;
}

function getPostgresConnection(): PDO {
    $pdo = new PDO("pgsql:dbname=system_tests_dbname;host=postgres;port=5433", "system_tests_user", "system_tests");
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    return $pdo;
}

function mysqlOperation(string $operation): void {
    $pdo = getMysqlConnection();
    switch ($operation) {
        case 'init':
            $pdo->exec("CREATE TABLE IF NOT EXISTS demo(id INT NOT NULL, name VARCHAR(20) NOT NULL, age INT NOT NULL, PRIMARY KEY (id))");
            // Insert rows idempotently
            $pdo->exec("INSERT IGNORE INTO demo (id, name, age) VALUES (1, 'test', 16)");
            $pdo->exec("INSERT IGNORE INTO demo (id, name, age) VALUES (2, 'test2', 17)");
            $pdo->exec("DROP PROCEDURE IF EXISTS test_procedure");
            $pdo->exec("CREATE PROCEDURE test_procedure(IN test_id INT, IN other VARCHAR(20))
BEGIN
    SELECT demo.id, demo.name, demo.age FROM demo WHERE demo.id = test_id;
END");
            break;
        case 'select':
            $stmt = $pdo->query("SELECT * from demo where id=1 or id IN (3, 4)");
            $stmt->fetchAll();
            break;
        case 'insert':
            try {
                $pdo->exec("insert into demo (id, name, age) values(3, 'test3', 163)");
            } catch (\PDOException $e) {
                // Row may already exist from a previous run; ignore duplicate key errors
            }
            break;
        case 'update':
            $pdo->exec("update demo set age=22 where id=1");
            break;
        case 'delete':
            $pdo->exec("delete from demo where id=2 or id=11111111");
            break;
        case 'procedure':
            $pdo->exec("call test_procedure(1, 'test')");
            break;
        case 'select_error':
            try {
                $pdo->query("SELECT * from demosssss where id=1 or id=233333");
            } catch (\PDOException $e) {
                // Expected error — span is created with error info
            }
            break;
    }
}

function postgresOperation(string $operation): void {
    $pdo = getPostgresConnection();
    switch ($operation) {
        case 'init':
            try {
                $pdo->exec("CREATE TABLE demo(id INT NOT NULL, name VARCHAR(20) NOT NULL, age INT NOT NULL, PRIMARY KEY (id))");
            } catch (\PDOException $e) {
                // Table may already exist
            }
            try {
                $pdo->exec("INSERT INTO demo (id, name, age) VALUES (1, 'test', 16)");
            } catch (\PDOException $e) {}
            try {
                $pdo->exec("INSERT INTO demo (id, name, age) VALUES (2, 'test2', 17)");
            } catch (\PDOException $e) {}
            $pdo->exec("CREATE OR REPLACE PROCEDURE helloworld(id int, other varchar(10))
LANGUAGE plpgsql
AS \$\$
BEGIN
    raise info 'Hello World';
END;
\$\$");
            break;
        case 'select':
            $stmt = $pdo->query("SELECT * from demo where id=1 or id IN (3, 4)");
            $stmt->fetchAll();
            break;
        case 'insert':
            try {
                $pdo->exec("insert into demo (id, name, age) values(3, 'test3', 163)");
            } catch (\PDOException $e) {}
            break;
        case 'update':
            $pdo->exec("update demo set age=22 where name like '%tes%'");
            break;
        case 'delete':
            $pdo->exec("delete from demo where id=2 or id=11111111");
            break;
        case 'procedure':
            $pdo->exec("call helloworld(1, 'test')");
            break;
        case 'select_error':
            try {
                $pdo->query("SELECT * from demosssssssss where id=1 or id=233333");
            } catch (\PDOException $e) {
                // Expected error — span is created with error info
            }
            break;
    }
}

switch ($service) {
    case 'mysql':
        mysqlOperation($operation);
        break;
    case 'postgresql':
        postgresOperation($operation);
        break;
    default:
        http_response_code(400);
        echo "Unsupported service: " . htmlspecialchars($service);
        exit;
}

echo "YEAH";
