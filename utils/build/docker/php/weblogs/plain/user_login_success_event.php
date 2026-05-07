<?php

\datadog\appsec\track_user_login_success_event($_GET['event_user_id'] ?? 'system_tests_user',
[
    'metadata0' => 'value0',
    'metadata1' => 'value1',
]);
?>
