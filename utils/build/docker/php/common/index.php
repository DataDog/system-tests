<?php

require_once 'cookie_manager.php';

$user = $_GET['username'] ?? getLoggedInCookie();
if (isset($user)) {
    \datadog\appsec\track_authenticated_user_event_automated($user);
}

header('Content-Type: text/plain');
header('Content-Length: 13');
echo "Hello world!\n";
