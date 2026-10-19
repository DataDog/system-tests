<?php

if (getenv('SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED') !== 'true') {
    http_response_code(404);
    exit;
}

$context = stream_context_create(array('http' => array(
    'method' => 'POST',
    'header' => "Content-Type: application/json\r\nConnection: close\r\n",
    'content' => file_get_contents('php://input'),
    'timeout' => 15,
    'ignore_errors' => true,
)));
$response = file_get_contents('http://127.0.0.1:7778/evaluate', false, $context);
if ($response === false) {
    http_response_code(502);
    exit;
}
header('Content-Type: application/json');
echo $response;
