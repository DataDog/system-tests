<?php

require_once '/var/www/html/vendor/autoload.php';

header('Content-Type: application/json');

try {
    // Configure Stripe client
    \Stripe\Stripe::setApiKey('sk_FAKE');
    \Stripe\Stripe::$apiBase = 'http://internal_server:8089';

    // Get JSON request body
    $input = file_get_contents('php://input');
    $data = json_decode($input, true);

    if (json_last_error() !== JSON_ERROR_NONE) {
        throw new Exception('Invalid JSON: ' . json_last_error_msg());
    }

    // Create payment intent with the request body data
    $result = \Stripe\PaymentIntent::create($data);

    // Return the result as JSON
    echo json_encode($result);
} catch (\Stripe\Exception\ApiErrorException $e) {
    http_response_code(500);
    echo json_encode(['error' => $e->getMessage()]);
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['error' => $e->getMessage()]);
}
