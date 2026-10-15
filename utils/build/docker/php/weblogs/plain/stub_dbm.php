<?php

/**
 * DBM comment format test endpoint.
 *
 * dd-trace-php modifies the SQL at the C level so neither PDO subclassing
 * nor DDTrace\hook_method sees the modified string before execution.
 * The modified SQL IS visible via PDOStatement::$queryString after the
 * call, because PDO stores the final SQL on the returned statement object.
 */

$integration = htmlspecialchars($_GET["integration"] ?? '');

$stmt = null;

if ($integration === "pdo-pgsql") {
    $con = new PDO(
        "pgsql:dbname=system_tests_dbname;host=postgres;port=5433",
        "system_tests_user",
        "system_tests"
    );
    $stmt = $con->query("SELECT version()");
} elseif ($integration === "pdo-mysql") {
    $con = new PDO(
        "mysql:dbname=mysql_dbname;host=mysqldb",
        "mysqldb",
        "mysqldb"
    );
    $stmt = $con->query("SELECT version()");
}

$captured = $stmt instanceof PDOStatement ? $stmt->queryString : null;

header('Content-Type: application/json');
echo json_encode([
    "status"      => "ok",
    "dbm_comment" => $captured,
]);
