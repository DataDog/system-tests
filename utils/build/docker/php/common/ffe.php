<?php

header('Content-Type: application/json');

$input = json_decode(file_get_contents('php://input'), true);

if (!is_array($input)) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid JSON body']);
    exit;
}

$flag = isset($input['flag']) ? $input['flag'] : null;
$variationType = isset($input['variationType']) ? $input['variationType'] : null;
$defaultValue = isset($input['defaultValue']) ? $input['defaultValue'] : null;
$targetingKey = array_key_exists('targetingKey', $input) ? $input['targetingKey'] : '';
$attributes = isset($input['attributes']) ? $input['attributes'] : [];

try {
    $provider = \DDTrace\FeatureFlags\Provider::getInstance();
    $provider->start();

    $result = $provider->evaluate($flag, $variationType, $defaultValue, $targetingKey, $attributes);

    // Flush exposure events immediately for system test observability
    $provider->flush();

    echo json_encode($result);
} catch (\Throwable $e) {
    echo json_encode(['value' => $defaultValue, 'reason' => 'ERROR', 'error' => $e->getMessage()]);
}
