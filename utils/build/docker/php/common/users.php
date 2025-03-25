<?php

\DDTrace\set_user($_GET["user"], [
    'name' => "usr.name",
    'email' => "usr.email",
    'session_id' => "usr.session_id",
    'role' => "usr.role",
    'scope' => "usr.scope"
]);

if (isset($_GET['user']) && $_GET['user'] == 'sdkUser') {
    \datadog\appsec\track_authenticated_user_event($_GET['user']);
    \datadog\appsec\track_authenticated_user_event_automated('social-security-id');
}

echo "OK";
?>

