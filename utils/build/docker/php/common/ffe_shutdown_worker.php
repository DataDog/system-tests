<?php

// A single PHP request remains alive across evaluations. Unlike FPM request
// teardown, this fixture exercises the native process-shutdown drain.
define('SYSTEM_TESTS_FFE_WORKER', true);
require __DIR__ . '/ffe.php';

$server = stream_socket_server('tcp://127.0.0.1:7778', $errno, $error);
if ($server === false) {
    throw new RuntimeException($error, $errno);
}
$stopping = false;
if (function_exists('pcntl_async_signals')) {
    pcntl_async_signals(true);
}
pcntl_signal(SIGTERM, function () use (&$stopping) { $stopping = true; });
pcntl_signal(SIGINT, function () use (&$stopping) { $stopping = true; });

while (!$stopping) {
    pcntl_signal_dispatch();
    $connection = @stream_socket_accept($server, 1);
    if ($connection === false) {
        continue;
    }
    stream_set_timeout($connection, 15);
    $length = 0;
    while (($line = fgets($connection)) !== false && trim($line) !== '') {
        if (stripos($line, 'Content-Length:') === 0) {
            $length = (int) trim(substr($line, strlen('Content-Length:')));
        }
    }
    $body = '';
    while (strlen($body) < $length) {
        $chunk = fread($connection, $length - strlen($body));
        if ($chunk === false || $chunk === '') {
            break;
        }
        $body .= $chunk;
    }
    $payload = json_decode($body, true);
    $details = dd_ffe_evaluate($payload['flag'], $payload['variationType'],
        $payload['defaultValue'], $payload['targetingKey'], $payload['attributes']);
    $response = json_encode(dd_ffe_details_payload($details), JSON_UNESCAPED_SLASHES);
    fwrite($connection, "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
        . strlen($response) . "\r\nConnection: close\r\n\r\n" . $response);
    fclose($connection);
}

fclose($server);
echo json_encode(array(
    'event' => 'system_tests.ffe.shutdown.server_closed',
    'timestamp' => (new DateTimeImmutable('now', new DateTimeZone('UTC')))->format('Y-m-d\TH:i:s.uP'),
)), PHP_EOL;
// No explicit flush: normal PHP request/module shutdown must deliver the event.
