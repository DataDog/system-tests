<?php
$body = file_get_contents("php://input");
$decoded = json_decode($body, 1);

if (isset($decoded['login']) && isset($decoded['exists']) && isset($decoded['metadata'])) {
    \datadog\appsec\v2\track_user_login_failure(
        $decoded['login'],
        $decoded['exists'] == "true" ? true : false,
        $decoded['metadata']
    );
} else if (isset($decoded['login']) && isset($decoded['exists'])) {
    \datadog\appsec\v2\track_user_login_failure(
        $decoded['login'],
        $decoded['exists'] == "true" ? true : false
    );
} else {
    \datadog\appsec\v2\track_user_login_failure(
        $decoded['login']
    );
}
?>
Done
