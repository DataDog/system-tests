<?php

require_once '/var/www/html/vendor/autoload.php';

header('Content-Type: application/json');

try {
    // Configure Stripe client
    \Stripe\Stripe::setApiKey('sk_FAKE');
    \Stripe\Stripe::$apiBase = 'http://internal_server:8089';

    // Get raw request body
    $payload = file_get_contents('php://input');

    // Get Stripe signature from header
    $sigHeader = $_SERVER['HTTP_STRIPE_SIGNATURE'] ?? '';

    // Webhook secret
    $webhookSecret = 'whsec_FAKE';

    // Construct and verify the event
    $event = \Stripe\Webhook::constructEvent(
        $payload,
        $sigHeader,
        $webhookSecret
    );

    // Return the event.data.object as JSON
    echo json_encode($event->data->object);
} catch (\Stripe\Exception\SignatureVerificationException $e) {
    http_response_code(403);
    echo json_encode(['error' => $e->getMessage()]);
} catch (Exception $e) {
    http_response_code(403);
    echo json_encode(['error' => $e->getMessage()]);
}
