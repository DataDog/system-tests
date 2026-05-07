<?php

const USERS = [
    'testnew' => [
        "id" => 'new-user',
        "password" => '1234',
        "username" => 'testnew',
        "email" => 'testnewuser@ddog.com'
    ],
];

function handlePost()
{
    $user = [
        "id" =>  USERS[$_POST['username']]['id'] ?? '',
        "username" => USERS[$_POST['username']]['username'] ?? $_POST['username'],
    ];
    \datadog\appsec\track_user_signup_event_automated($user['username'], $user['id'], []);
}

function checkSdk()
{
    if (!isset($_REQUEST['sdk_event'])) {
        return;
    }

    $event = $_REQUEST['sdk_event'];
    $user = $_REQUEST['sdk_user'];
    $mail = $_REQUEST['sdk_mail'];

    if ($event == 'signup') {
        \datadog\appsec\track_user_signup_event($user, ["email" => $mail]);
        http_response_code(200);
    }
}

if ($_SERVER['REQUEST_METHOD'] != 'POST') {
    return;
}

handlePost();

checkSdk();
