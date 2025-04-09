<?php

require_once 'cookie_manager.php';

if (!isset($_SERVER['HTTP_X_DATADOG_ORIGIN'])) {
    \datadog\appsec\track_authenticated_user_event_automated($_GET['username'] ?? 'social-security-id');
}

$user = getLoggedInCookie();
if (isset($user)) {
    \datadog\appsec\track_authenticated_user_event_automated($user);
}

phpinfo();