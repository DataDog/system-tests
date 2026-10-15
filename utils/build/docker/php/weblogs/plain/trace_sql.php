<?php

// Disable the automatic HTTP root span so the PDO span itself is the root,
// giving it the correct span type ("sql") that assert_trace_exists checks.
ini_set("datadog.trace.generate_root_span", 0);

try {
    $pdo = new PDO("mysql:dbname=mysql_dbname;host=mysqldb", "mysqldb", "mysqldb");
    $pdo->query("SELECT 1");
} catch (\Exception $e) {
    // Ignore connection issues
}

echo "OK";
