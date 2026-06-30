<?php

function dd_ffe_json_response($statusCode, array $payload)
{
    header('Content-Type: application/json');
    http_response_code($statusCode);
    echo json_encode($payload, JSON_UNESCAPED_SLASHES);
}

function dd_ffe_error_response($statusCode, $errorCode, $errorMessage)
{
    dd_ffe_json_response($statusCode, array(
        'value' => null,
        'reason' => 'ERROR',
        'variant' => null,
        'errorCode' => $errorCode,
        'errorMessage' => $errorMessage,
        'providerState' => array('ready' => false),
    ));
}

function dd_ffe_flush_exposures()
{
    if (function_exists('DDTrace\\Testing\\flush_ffe_exposures')) {
        return \DDTrace\Testing\flush_ffe_exposures();
    }

    return null;
}

function dd_ffe_read_payload()
{
    $rawBody = file_get_contents('php://input');
    if ($rawBody === false || $rawBody === '') {
        return array();
    }

    $payload = json_decode($rawBody, true);
    if (json_last_error() !== JSON_ERROR_NONE || !is_array($payload)) {
        dd_ffe_error_response(400, 'INVALID_REQUEST', 'Expected a JSON object request body.');
        exit;
    }

    return $payload;
}

function dd_ffe_normalized_variation_type($variationType)
{
    return strtoupper(str_replace('-', '_', (string) $variationType));
}

function dd_ffe_normalize_default_value($defaultValue, $variationType)
{
    switch (dd_ffe_normalized_variation_type($variationType)) {
        case 'BOOLEAN':
            return is_bool($defaultValue) ? $defaultValue : (bool) $defaultValue;
        case 'STRING':
            return is_string($defaultValue) ? $defaultValue : (string) $defaultValue;
        case 'INTEGER':
            return is_int($defaultValue) ? $defaultValue : (int) $defaultValue;
        case 'NUMERIC':
        case 'FLOAT':
        case 'DOUBLE':
            return is_int($defaultValue) || is_float($defaultValue) ? $defaultValue : (float) $defaultValue;
        case 'JSON':
        case 'OBJECT':
            return is_array($defaultValue) ? $defaultValue : array();
        default:
            return $defaultValue;
    }
}

function dd_ffe_scalar_attributes(array $attributes)
{
    $normalized = array();
    foreach ($attributes as $key => $value) {
        if (is_bool($value) || is_int($value) || is_float($value) || is_string($value)) {
            $normalized[(string) $key] = $value;
        }
    }

    return $normalized;
}

function dd_ffe_evaluate_with_client($flagKey, $variationType, $defaultValue, $targetingKey, array $attributes)
{
    if (!class_exists('\\DDTrace\\FeatureFlags\\Client')) {
        return null;
    }

    if (method_exists('\\DDTrace\\FeatureFlags\\Client', 'create')) {
        $client = \DDTrace\FeatureFlags\Client::create();
    } else {
        $client = new \DDTrace\FeatureFlags\Client();
    }

    $context = array(
        'targetingKey' => $targetingKey,
        'attributes' => $attributes,
    );

    switch (dd_ffe_normalized_variation_type($variationType)) {
        case 'BOOLEAN':
            return $client->getBooleanDetails($flagKey, $defaultValue, $context);
        case 'STRING':
            return $client->getStringDetails($flagKey, $defaultValue, $context);
        case 'INTEGER':
            return $client->getIntegerDetails($flagKey, $defaultValue, $context);
        case 'NUMERIC':
        case 'FLOAT':
        case 'DOUBLE':
            return $client->getFloatDetails($flagKey, $defaultValue, $context);
        case 'JSON':
        case 'OBJECT':
            return $client->getObjectDetails($flagKey, is_array($defaultValue) ? $defaultValue : array(), $context);
        default:
            throw new InvalidArgumentException('Unsupported variationType: ' . (string) $variationType);
    }
}

function dd_ffe_warning_handler($severity, $message)
{
    if ($severity === E_USER_WARNING && strpos($message, 'Datadog-backed PHP feature flag evaluation') !== false) {
        return true;
    }

    return false;
}

function dd_ffe_evaluate($flagKey, $variationType, $defaultValue, $targetingKey, array $attributes)
{
    set_error_handler('dd_ffe_warning_handler');
    try {
        return dd_ffe_evaluate_with_client($flagKey, $variationType, $defaultValue, $targetingKey, $attributes);
    } finally {
        restore_error_handler();
    }
}

function dd_ffe_should_wait_for_flag(array $payload)
{
    return isset($payload['waitForFlag']) && $payload['waitForFlag'] === true;
}

function dd_ffe_flag_wait_timeout_ms(array $payload)
{
    $timeoutMs = isset($payload['flagWaitTimeoutMs']) ? (int) $payload['flagWaitTimeoutMs'] : 5000;
    return max(0, min($timeoutMs, 30000));
}

function dd_ffe_should_retry_evaluation($details)
{
    if (!method_exists($details, 'getErrorCode')) {
        return false;
    }

    $errorCode = $details->getErrorCode();
    return $errorCode === 'FLAG_NOT_FOUND' || $errorCode === 'PROVIDER_NOT_READY';
}

function dd_ffe_evaluate_until_flag_ready(
    $flagKey,
    $variationType,
    $defaultValue,
    $targetingKey,
    array $attributes,
    $timeoutMs,
    &$attempts
) {
    $deadline = microtime(true) * 1000 + $timeoutMs;
    $attempts = 0;
    $details = null;

    do {
        $attempts++;
        $details = dd_ffe_evaluate($flagKey, $variationType, $defaultValue, $targetingKey, $attributes);
        if (!dd_ffe_should_retry_evaluation($details)) {
            break;
        }
        usleep(10000);
    } while (microtime(true) * 1000 < $deadline);

    return $details;
}

function dd_ffe_details_payload($details)
{
    $payload = array(
        'value' => $details->getValue(),
        'reason' => $details->getReason(),
        'variant' => $details->getVariant(),
        'errorCode' => $details->getErrorCode(),
        'errorMessage' => $details->getErrorMessage(),
        'flagMetadata' => $details->getFlagMetadata(),
        'exposureData' => $details->getExposureData(),
        'providerState' => $details->getProviderState(),
    );

    if (method_exists($details, 'getValueType')) {
        $payload['valueType'] = $details->getValueType();
    }

    return $payload;
}

$payload = dd_ffe_read_payload();

if (!isset($payload['flag']) || !is_string($payload['flag']) || $payload['flag'] === '') {
    dd_ffe_error_response(400, 'INVALID_REQUEST', 'Expected non-empty string field: flag.');
    exit;
}

if (!array_key_exists('variationType', $payload) || !is_string($payload['variationType'])) {
    dd_ffe_error_response(400, 'INVALID_REQUEST', 'Expected string field: variationType.');
    exit;
}

if (!array_key_exists('defaultValue', $payload)) {
    dd_ffe_error_response(400, 'INVALID_REQUEST', 'Expected field: defaultValue.');
    exit;
}

$flagKey = $payload['flag'];
$variationType = $payload['variationType'];
$defaultValue = dd_ffe_normalize_default_value($payload['defaultValue'], $variationType);
$targetingKey = isset($payload['targetingKey']) && $payload['targetingKey'] !== null
    ? (string) $payload['targetingKey']
    : null;
$targetingKeys = isset($payload['targetingKeys']) && is_array($payload['targetingKeys']) && count($payload['targetingKeys']) > 0
    ? array_values(array_map('strval', $payload['targetingKeys']))
    : array($targetingKey);
$attributes = isset($payload['attributes']) && is_array($payload['attributes'])
    ? dd_ffe_scalar_attributes($payload['attributes'])
    : array();

try {
    $details = null;
    $flagWaitAttempts = 0;
    $waitForFlag = dd_ffe_should_wait_for_flag($payload);
    foreach ($targetingKeys as $key) {
        if ($waitForFlag) {
            $attempts = 0;
            $details = dd_ffe_evaluate_until_flag_ready(
                $flagKey,
                $variationType,
                $defaultValue,
                $key,
                $attributes,
                dd_ffe_flag_wait_timeout_ms($payload),
                $attempts
            );
            $flagWaitAttempts += $attempts;
        } else {
            $details = dd_ffe_evaluate($flagKey, $variationType, $defaultValue, $key, $attributes);
        }
    }
    if ($details !== null) {
        $response = dd_ffe_details_payload($details);
        if ($waitForFlag) {
            $response['flagWaitAttempts'] = $flagWaitAttempts;
        }
        $response['count'] = count($targetingKeys);
        $response['exposuresFlushed'] = dd_ffe_flush_exposures();
        dd_ffe_json_response(200, $response);
        return;
    }
} catch (Throwable $exception) {
    dd_ffe_json_response(200, array(
        'value' => $defaultValue,
        'reason' => 'ERROR',
        'variant' => null,
        'errorCode' => 'PROVIDER_NOT_READY',
        'errorMessage' => $exception->getMessage(),
        'providerState' => array(
            'ready' => false,
            'productionRuntime' => false,
        ),
    ));
    return;
}

dd_ffe_json_response(200, array(
    'value' => $defaultValue,
    'reason' => 'ERROR',
    'variant' => null,
    'errorCode' => 'PROVIDER_NOT_READY',
    'errorMessage' => 'Datadog-backed PHP feature flag evaluation is not wired in this weblog yet.',
    'providerState' => array(
        'ready' => false,
        'productionRuntime' => false,
    ),
));
