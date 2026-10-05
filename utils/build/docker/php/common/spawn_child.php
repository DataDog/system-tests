<?php
// Spawn child via exec (PHP does not support fork in web context).
// Params: sleep, crash, fork (all required). Returns 400 if fork=true.

$sleep = $_GET['sleep'] ?? '';
$crash = strtolower($_GET['crash'] ?? '');
$fork = strtolower($_GET['fork'] ?? '');

if ($sleep === '' || !ctype_digit($sleep) || (int) $sleep < 0) {
    http_response_code(400);
    echo 'sleep required';
    exit;
}
if ($crash !== 'true' && $crash !== 'false') {
    http_response_code(400);
    echo 'crash required (boolean)';
    exit;
}
if ($fork !== 'true' && $fork !== 'false') {
    http_response_code(400);
    echo 'fork required (boolean)';
    exit;
}
if ($fork === 'true') {
    http_response_code(400);
    echo 'fork not supported';
    exit;
}

$sleepSec = (int) $sleep;
$doCrash = $crash === 'true';

$cmd = sprintf(
    'sleep %d && %s',
    $sleepSec,
    $doCrash ? 'kill -SEGV $$' : 'exit 0'
);
$output = [];
$returnVar = 0;
exec($cmd . ' 2>&1', $output, $returnVar);

header('Content-Type: text/plain');
echo 'Child process exited with status ' . $returnVar;
