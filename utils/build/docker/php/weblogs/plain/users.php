<?php

require_once 'appsec_compat.php';

\DDTrace\set_user($_GET["user"], [
    'name' => "usr.name",
    'email' => "usr.email",
    'session_id' => "usr.session_id",
    'role' => "usr.role",
    'scope' => "usr.scope"
]);

if (isset($_GET['user']) && $_GET['user'] == 'sdkUser') {
    \datadog\appsec\track_authenticated_user_event($_GET['user']);
    if (_dd_appsec_new_api()) {
        \datadog\appsec\internal\track_authenticated_user_event_automated('custom', 'social-security-id');
    } else {
        \datadog\appsec\track_authenticated_user_event_automated('social-security-id');
    }
}

echo "OK";
?>
