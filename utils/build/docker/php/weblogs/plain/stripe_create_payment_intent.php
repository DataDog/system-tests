<?php

require_once __DIR__ . '/vendor/autoload.php';

header('Content-Type: application/json');

\Stripe\Stripe::setApiKey('sk_FAKE');
\Stripe\Stripe::$apiBase = 'http://internal_server:8089';

$body = json_decode(file_get_contents('php://input'), true) ?? [];

try {
    $result = \Stripe\PaymentIntent::create($body);
    echo json_encode($result);
} catch (\Exception $e) {
    http_response_code(500);
    echo json_encode(['error' => $e->getMessage()]);
}
