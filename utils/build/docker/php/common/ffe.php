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
    // Use OpenFeature API if available, fall back to direct provider
    if (class_exists('\OpenFeature\API')) {
        $provider = new \DDTrace\OpenFeature\DataDogProvider();
        \OpenFeature\API::setProvider($provider);
        $client = \OpenFeature\API::getClient();

        $context = new \OpenFeature\implementation\flags\EvaluationContext(
            $targetingKey,
            new \OpenFeature\implementation\flags\Attributes($attributes)
        );

        $value = match ($variationType) {
            'BOOLEAN' => $client->getBooleanValue($flag, (bool) $defaultValue, $context),
            'STRING' => $client->getStringValue($flag, (string) $defaultValue, $context),
            'INTEGER' => $client->getIntegerValue($flag, (int) $defaultValue, $context),
            'NUMERIC' => $client->getFloatValue($flag, (float) $defaultValue, $context),
            'JSON' => $client->getObjectValue($flag, is_array($defaultValue) ? $defaultValue : [], $context),
            default => $defaultValue,
        };
    } else {
        // Fallback to direct provider (no OpenFeature SDK installed)
        $provider = \DDTrace\FeatureFlags\Provider::getInstance();
        $provider->start();
        $result = $provider->evaluate($flag, $variationType, $defaultValue, $targetingKey, $attributes);
        $value = $result['value'];
    }

    // Flush exposure events immediately for system test observability
    \DDTrace\FeatureFlags\Provider::getInstance()->flush();

    echo json_encode(['value' => $value]);
} catch (\Throwable $e) {
    echo json_encode(['value' => $defaultValue, 'error' => $e->getMessage()]);
}
