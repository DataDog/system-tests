<?php

// Disable the automatic HTTP root span so the MongoDB span itself is the root.
ini_set("datadog.trace.generate_root_span", 0);

if (!extension_loaded('mongodb')) {
    http_response_code(501);
    echo 'mongodb extension not available';
    exit;
}

// Use the low-level MongoDB extension directly — ddtrace instruments it automatically.
$manager = new \MongoDB\Driver\Manager('mongodb://mongodb:27017');
$query = new \MongoDB\Driver\Query([]);
$manager->executeQuery('system_tests.traces', $query);

echo 'OK';
