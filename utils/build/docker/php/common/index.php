<?php phpinfo();

\datadog\appsec\track_authenticated_user_event_automated($_GET['username'] ?? 'social-security-id');
