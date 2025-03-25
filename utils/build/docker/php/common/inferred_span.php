<?php

$statusCodeStr = isset($_GET['status_code']) ? $_GET['status_code'] : '';

// Default status code
$statusCode = 200;

if ($statusCodeStr !== '') {
    $statusCode = intval($statusCodeStr);

    if ($statusCode == 0 && $statusCodeStr !== '0') {
        $statusCode = 400;
    }
}

error_log("Received an API Gateway request:");
foreach ($_SERVER as $key => $value) {
    if (strpos($key, 'HTTP_') === 0) { // Check for HTTP headers
        error_log("$key: $value");
    }
}

// Send the response
http_response_code($statusCode);
echo "ok";
?>
