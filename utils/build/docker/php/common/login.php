<?php


const USERS = [
	'test' => [
		"id" => 'social-security-id',
		"password" => '1234',
		"username" => 'test',
		"email" => 'testuser@ddog.com'
	],
	'testuuid' => [
		"id" => '591dc126-8431-4d0f-9509-b23318d3dce4',
		"password" => '1234',
		"username" => 'testuuid',
		"email" => 'testuseruuid@ddog.com'
	]
];


function handlePost()
{
	if (!isset(USERS[$_POST['username']])) {
		\datadog\appsec\track_user_login_failure_event($_POST['username'], false, [], true);
		http_response_code(401);
		return;
	}

	$user = USERS[$_POST['username']];
	if ($user['password'] != $_POST['password']) {
		\datadog\appsec\track_user_login_failure_event($user['id'], true, $user, true);
		http_response_code(401);
		return;
	}

	\datadog\appsec\track_user_login_success_event($user['id'], $user, true);
}

function handleGet()
{
	
}

function checkSdk()
{
	if (!isset($_REQUEST['sdk_event'])) {
		return;
	}

	$event = $_REQUEST['sdk_event'];
	$user = $_REQUEST['sdk_user'];
	$mail = $_REQUEST['sdk_mail'];
	$exists = $_REQUEST['sdk_user_exists'];

	if ($event == 'success') {
		\datadog\appsec\track_user_login_success_event($user, ["email" => $mail]);
		http_response_code(200);
	} else {
		\datadog\appsec\track_user_login_failure_event($user, $exists, ["email" => $mail]);
		http_response_code(401);
	}
}

if ($_GET['auth'] != 'local') {
	return;
}


$_SERVER['REQUEST_METHOD'] === 'POST' ? handlePost(): handleGet();

checkSdk();
