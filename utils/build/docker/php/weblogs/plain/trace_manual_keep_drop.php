<?php

$decision = $_GET["decision"] ?? '';
if ($decision !== 'keep' && $decision !== 'drop') {
    http_response_code(400);
    header('Content-Type: text/plain');
    echo 'decision must be keep or drop';
    exit;
}

$span = \DDTrace\active_span();
$span->meta[$decision === 'keep' ? \DDTrace\Tag::MANUAL_KEEP : \DDTrace\Tag::MANUAL_DROP] = true;

header('Content-Type: text/plain');
echo 'OK';
