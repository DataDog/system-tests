<?php
// pass user ID as integer to test that it ends up in meta not metrics
\datadog\appsec\track_user_login_success_event(123456,
[
    'metadata0' => 'value0',
    'metadata1' => 'value1',
]);
?>
