<?php
$body = file_get_contents("php://input");
$decoded = json_decode($body, 1);

if (isset($decoded['login']) && isset($decoded['user_id']) && isset($decoded['metadata'])) {
    \DDTrace\ATO\V2\track_user_login_success(
        $decoded['login'],
        $decoded['user_id'],
        $decoded['metadata']
    );
} else if (isset($decoded['login']) && isset($decoded['user_id'])) {
    \DDTrace\ATO\V2\track_user_login_success(
        $decoded['login'],
        $decoded['user_id']
    );
} else {
    \DDTrace\ATO\V2\track_user_login_success(
        $decoded['login']
    );
}
?>
Done
