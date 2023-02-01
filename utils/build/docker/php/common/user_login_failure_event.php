<?php
// pass user ID as integer to test that it ends up in meta not metrics
\datadog\appsec\track_user_login_failure_event(123456, true,
[
    'metadata0' => 'value0',
    'metadata1' => 'value1',
]);
?>
