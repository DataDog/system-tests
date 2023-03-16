<?php

\DDTrace\set_user($_GET["user"], [
    'name' => "usr.name",
    'email' => "usr.email",
    'session_id' => "usr.session_id",
    'role' => "usr.role",
    'scope' => "usr.scope"
]);

echo "OK";
?>