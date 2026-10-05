<?php

\datadog\appsec\track_custom_event($_GET['event_name'] ?? 'system_tests_event',
[
    'metadata0' => 'value0',
    'metadata1' => 'value1',
]);
?>
