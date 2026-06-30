<?php

\datadog\appsec\track_user_login_failure_event($_GET['event_user_id'] ?? 'system_tests_user', $_GET['event_user_exists'] ?? true,
[
    'metadata0' => 'value0',
    'metadata1' => 'value1',
]);
?>
