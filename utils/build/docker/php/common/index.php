<?php phpinfo();

if (!isset($_SERVER['HTTP_X_DATADOG_ORIGIN'])) {
    \datadog\appsec\track_authenticated_user_event_automated($_GET['username'] ?? 'social-security-id');
}
