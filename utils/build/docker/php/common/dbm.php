<?php

$integration = htmlspecialchars($_GET["integration"]);
$query = "SELECT version()";

if ($integration == "pdo") {
    // // Running MySql query
    $connection = new PDO("mysql:dbname=world;host=mysqldb", "mysqldb", "mysqldb");
    $connection->query($query);

    // Running Postgres query
    $connection = new PDO("pgsql:dbname=system_tests;host=postgres;port=5433", "system_tests_user", "system_tests");
    $connection->query($query);
} elseif ($integration == "mysqli") {
    $connection = new mysqli("mysqldb", "mysqldb", "mysqldb", "world");
    $connection->query($query);
}

?>
