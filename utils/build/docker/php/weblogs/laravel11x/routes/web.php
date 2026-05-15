<?php

use App\Http\Controllers\LoginController;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    Auth::user();
    return response("Hello world!\n", 200, [
        'Content-Type' => 'text/plain; charset=utf-8',
        'Content-Length' => '13',
    ]);
});

Route::get('/healthcheck', function () {
    $version = phpversion('ddtrace') ?: 'unknown';

    return response()->json([
        'status'  => 'ok',
        'library' => ['name' => 'php', 'version' => $version],
    ]);
});

Route::get('/status', function (Request $request) {
    $code = intval($request->query('code', 200));

    return response('', $code);
});

Route::get('/make_distant_call', function (Request $request) {
    $url = $request->query('url', '');
    if ($url === '') {
        return response()->json(['error' => 'url parameter required'], 400);
    }
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HEADER, false);
    curl_setopt($ch, CURLINFO_HEADER_OUT, true);
    $responseHeaders = [];
    curl_setopt($ch, CURLOPT_HEADERFUNCTION, function ($curl, $header) use (&$responseHeaders) {
        $len = strlen($header);
        $parts = explode(':', $header, 2);
        if (count($parts) === 2) {
            $responseHeaders[strtolower(trim($parts[0]))] = trim($parts[1]);
        }

        return $len;
    });
    curl_exec($ch);
    $statusCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $requestHeaders = [];
    $rawRequestHeaders = curl_getinfo($ch, CURLINFO_HEADER_OUT);
    if ($rawRequestHeaders) {
        foreach (explode("\r\n", $rawRequestHeaders) as $line) {
            if (strpos($line, ':') !== false) {
                [$key, $value] = explode(':', $line, 2);
                $requestHeaders[strtolower(trim($key))] = trim($value);
            }
        }
    }
    curl_close($ch);

    return response()->json([
        'url'              => $url,
        'status_code'      => $statusCode,
        'request_headers'  => $requestHeaders,
        'response_headers' => $responseHeaders,
    ]);
});

Route::get('/read_file', function (Request $request) {
    $file = $request->query('file', '');
    $content = @file_get_contents($file);

    return response($content === false ? '' : $content, 200, ['Content-Type' => 'text/plain']);
});

Route::get('/users', function (Request $request) {
    $user = $request->query('user');

    \DDTrace\set_user($user, [
        'name'       => 'usr.name',
        'email'      => 'usr.email',
        'session_id' => 'usr.session_id',
        'role'       => 'usr.role',
        'scope'      => 'usr.scope',
    ]);

    if ($user === 'sdkUser') {
        \datadog\appsec\track_authenticated_user_event($user);
    }

    return response('OK', 200, ['Content-Type' => 'text/plain']);
});

Route::get('/identify', function () {
    \DDTrace\set_user('usr.id', [
        'name'       => 'usr.name',
        'email'      => 'usr.email',
        'session_id' => 'usr.session_id',
        'role'       => 'usr.role',
        'scope'      => 'usr.scope',
    ]);

    return response('', 200);
});

Route::get('/identify-propagate', function () {
    \DDTrace\set_user('usr.id', [
        'name'       => 'usr.name',
        'email'      => 'usr.email',
        'session_id' => 'usr.session_id',
        'role'       => 'usr.role',
        'scope'      => 'usr.scope',
    ], true);

    return response('', 200);
});

$wafResponse = static fn () => response('Hello, WAF!', 200, ['Content-Type' => 'text/plain']);

Route::match(['get', 'post'], '/waf', $wafResponse);
Route::match(['get', 'post'], '/waf/', $wafResponse);
Route::match(['get', 'post'], '/waf/{path}', $wafResponse)->where('path', '.*');

Route::get('/headers', function () {
    return response('Hello, headers!', 200, [
        'Content-Type'     => 'text/plain',
        'Content-Length'   => '15',
        'Content-Language' => 'en-US',
    ]);
});

Route::get('/session/new', function () {
    session()->start();

    return response(session()->getId(), 200, ['Content-Type' => 'text/plain']);
});

Route::get('/user_login_success_event', function (Request $request) {
    \datadog\appsec\track_user_login_success_event($request->query('event_user_id', 'system_tests_user'), [
        'metadata0' => 'value0',
        'metadata1' => 'value1',
    ]);

    return response('', 200);
});

Route::get('/user_login_failure_event', function (Request $request) {
    $exists = $request->query('event_user_exists', 'true');
    $existsBool = filter_var($exists, FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE);
    if ($existsBool === null) {
        $existsBool = true;
    }
    \datadog\appsec\track_user_login_failure_event(
        $request->query('event_user_id', 'system_tests_user'),
        $existsBool,
        [
            'metadata0' => 'value0',
            'metadata1' => 'value1',
        ]
    );

    return response('', 200);
});

Route::get('/custom_event', function (Request $request) {
    \datadog\appsec\track_custom_event($request->query('event_name', 'system_tests_event'), [
        'metadata0' => 'value0',
        'metadata1' => 'value1',
    ]);

    return response('', 200);
});

Route::post('/shell_execution', function (Request $request) {
    $raw = $request->getContent();
    $spec = json_decode($raw, true) ?: [];
    $command = $spec['command'] ?? '';
    $options = $spec['options'] ?? [];
    $args = $spec['args'] ?? [];
    $isShell = ! empty($options['shell']);

    if (PHP_VERSION_ID < 70400 && ! $isShell) {
        return response('PHP version must be at least 7.4.0 to run this command in non-shell mode', 500);
    }

    if (is_string($args)) {
        $args = preg_split('/\s+/', $args);
    }
    $c = array_merge([$command], $args);
    if ($isShell) {
        $c = implode(' ', $c);
    }
    $p = proc_open($c, [1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
    if (! is_resource($p)) {
        return response('Failed to open process', 500);
    }
    $stdout = stream_get_contents($pipes[1]);
    fclose($pipes[1]);
    $stderr = stream_get_contents($pipes[2]);
    fclose($pipes[2]);
    $out = "STDOUT:\n$stdout\nSTDERR:\n$stderr\nexit code: ".proc_close($p)."\n";

    return response($out, 200, ['Content-Type' => 'text/plain']);
});

Route::match(['get', 'post', 'options'], '/tag_value/{tag_value}/{status_code}', function (string $tag_value, string $status_code, Request $request) {
    $responseCodeStr = strtok($status_code, '?') ?: $status_code;
    if (! is_numeric($responseCodeStr)) {
        return response('Error parsing uri', 400);
    }
    $responseCode = (int) $responseCodeStr;
    \datadog\appsec\track_custom_event('system_tests_appsec_event', [
        'value' => $tag_value,
    ]);
    foreach ($request->query() as $key => $value) {
        header(ucwords($key).': '.$value);
    }
    $body = 'Value tagged';
    $payloadPrefix = 'payload_in_response_body';
    if (str_starts_with($tag_value, $payloadPrefix) && $request->isMethod('POST')) {
        $parsed = $request->all();

        return response()->json(['payload' => $parsed], $responseCode === 200 ? 200 : $responseCode, [
            'Content-Type' => 'application/json',
        ]);
    }
    if ($responseCode !== 200) {
        return response($body, $responseCode, ['Content-Type' => 'text/plain']);
    }

    return response($body, 200, ['Content-Type' => 'text/plain']);
});

Route::get('/params/{param}', function () {
    return response('ok', 200, ['Content-Type' => 'text/plain']);
});

Route::get('/dbm', function (Request $request) {
    $integration = $request->query('integration', '');
    $query = 'SELECT version()';

    if ($integration === 'pdo-mysql') {
        $connection = new PDO('mysql:dbname=mysql_dbname;host=mysqldb', 'mysqldb', 'mysqldb');
        $connection->query($query);
    } elseif ($integration === 'pdo-pgsql') {
        $connection = new PDO('pgsql:dbname=system_tests_dbname;host=postgres;port=5433', 'system_tests_user', 'system_tests');
        $connection->query($query);
    } elseif ($integration === 'mysqli') {
        $connection = new mysqli('mysqldb', 'mysqldb', 'mysqldb', 'mysql_dbname');
        $connection->query($query);
    }

    return response('', 200);
});

Route::get('/log/library', function (Request $request) {
    $dir = env('SYSTEM_TESTS_LOGS', '/var/log/system-tests');
    if (! is_dir($dir)) {
        @mkdir($dir, 0777, true);
    }
    $msg = $request->query('msg', '');
    if ($msg !== '') {
        file_put_contents($dir.'/helper.log', date('c').' '.$msg."\n", FILE_APPEND);
    }

    return response('', 200);
});

Route::match(['GET', 'POST'], '/login', [LoginController::class, 'login']);

Route::post('/signup', [LoginController::class, 'signup']);
