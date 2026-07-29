<?php

$decision = $_GET["decision"] ?? '';
if ($decision !== 'keep' && $decision !== 'drop') {
    http_response_code(400);
    header('Content-Type: text/plain');
    echo 'decision must be keep or drop';
    exit;
}

// set_priority_sampling is what \DDTrace\Span::setTag does for the manual.keep / manual.drop tags,
// and unlike writing the tag into the root span's meta it also overrides a decision propagated upstream.
\DDTrace\set_priority_sampling(
    $decision === 'keep' ? DD_TRACE_PRIORITY_SAMPLING_USER_KEEP : DD_TRACE_PRIORITY_SAMPLING_USER_REJECT
);

header('Content-Type: text/plain');
echo 'OK';
