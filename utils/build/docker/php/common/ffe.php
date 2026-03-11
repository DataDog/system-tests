<?php

header('Content-Type: application/json');

// Load Composer autoload so that OTel SDK classes are available for metrics
if (file_exists(__DIR__ . '/vendor/autoload.php')) {
    require_once __DIR__ . '/vendor/autoload.php';
    // Initialize OTel SDK so metrics can be exported (requires OTEL_PHP_AUTOLOAD_ENABLED=true)
    if (class_exists('\OpenTelemetry\SDK\SdkAutoloader')) {
        \OpenTelemetry\SDK\SdkAutoloader::autoload();
    }
}

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

    // On the first request to a PHP-FPM worker, the RC config may not yet be
    // loaded into FFE_STATE (the VM interrupt that calls ddog_process_remote_configs
    // fires at opcode boundaries, but hasn't run before start() is called).
    // Each usleep() allows the pending SIGVTALRM interrupt to be processed.
    if (!$provider->isReady()) {
        for ($i = 0; $i < 5 && !$provider->isReady(); $i++) {
            usleep(100000); // 100ms — allow VM interrupt to process RC update
            $provider->start(); // re-check after interrupt may have fired
        }
    }

    $result = $provider->evaluate($flag, $variationType, $defaultValue, $targetingKey, $attributes);

    // Flush exposure events immediately for system test observability
    $provider->flush();

    // Flush OTel metrics immediately so the agent receives them before the test reads
    $meterProvider = \OpenTelemetry\API\Globals::meterProvider();
    if (method_exists($meterProvider, 'forceFlush')) {
        $meterProvider->forceFlush();
    }

    echo json_encode($result);
} catch (\Throwable $e) {
    echo json_encode(['value' => $defaultValue, 'reason' => 'ERROR', 'error' => $e->getMessage()]);
}
