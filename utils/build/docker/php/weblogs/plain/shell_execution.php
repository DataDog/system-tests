<?php

$spec = json_decode(stream_get_contents(fopen('php://input', 'rb')), true);

$command = $spec['command'];
$options = $spec['options'] ?? [];
$args = $spec['args'] ?? [];

$isShell = !empty($options['shell']);

if (!$isShell && PHP_VERSION_ID < 70400) {
    http_send_status(500);
    error_log('PHP version must be at least 7.4.0 to run this command in non-shell mode');
    die('PHP version must be at least 7.4.0 to run this command in non-shell mode');
}

if (is_string($args)) {
    $args = preg_split('/\s+/', $args);
}

$c = array_merge([$command], $args);
if ($isShell) {
    $c = implode(' ', $c); // purposefully not escaped
}

$p = proc_open($c, [1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
if (!is_resource($p)) {
    http_send_status(500);
    error_log("Failed to open process: $p");
    die('Failed to open process');
}

$stdout = stream_get_contents($pipes[1]);
fclose($pipes[1]);
$stderr = stream_get_contents($pipes[2]);
fclose($pipes[2]);

echo "STDOUT:\n$stdout\n";
echo "STDERR:\n$stderr\n";

echo "exit code: " . proc_close($p), "\n";
