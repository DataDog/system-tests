<?php

require_once __DIR__ . '/vendor/autoload.php';

header('Content-Type: application/json');

\Stripe\Stripe::setApiKey('sk_FAKE');

$payload   = file_get_contents('php://input');
$sigHeader = $_SERVER['HTTP_STRIPE_SIGNATURE'] ?? '';

try {
    $event = \Stripe\Webhook::constructEvent($payload, $sigHeader, 'whsec_FAKE');
    echo json_encode($event->data->object);
} catch (\Stripe\Exception\SignatureVerificationException $e) {
    http_response_code(403);
    echo json_encode(['error' => $e->getMessage()]);
} catch (\Exception $e) {
    http_response_code(403);
    echo json_encode(['error' => $e->getMessage()]);
}
