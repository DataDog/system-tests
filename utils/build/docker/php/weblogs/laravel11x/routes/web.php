<?php

use App\Http\Controllers\LoginController;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Route;

Route::get('/', function (Request $request) {
    Auth::user(); // trigger authenticated user tracking for logged-in sessions
    return response('Hello World!', 200)->header('Content-Type', 'text/plain');
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

Route::any('/waf', function () {
    return response('Hello, WAF!');
});

Route::any('/waf/{path}', function () {
    return response('Hello, WAF!');
})->where('path', '.*');

Route::get('/headers', function () {
    return response('Hello, headers!', 200)
        ->header('Content-Language', 'en-US')
        ->header('Content-Length', '15');
});

Route::get('/sample_rate_route/{i}', function () {
    return response('OK');
});

Route::get('/make_distant_call', function (Request $request) {
    $url = $request->query('url', '');
    if (!$url) {
        return response()->json(['error' => 'url parameter required'], 400);
    }

    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HEADER, false);
    curl_setopt($ch, CURLINFO_HEADER_OUT, true);

    $responseHeaders = [];
    curl_setopt($ch, CURLOPT_HEADERFUNCTION, function ($curl, $header) use (&$responseHeaders) {
        $len   = strlen($header);
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
            if (str_contains($line, ':')) {
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
    return response(file_get_contents($file));
});

Route::get('/identify', function () {
    \DDTrace\set_user('usr.id', [
        'name'       => 'usr.name',
        'email'      => 'usr.email',
        'session_id' => 'usr.session_id',
        'role'       => 'usr.role',
        'scope'      => 'usr.scope',
    ]);
    return response('OK');
});

Route::get('/identify-propagate', function () {
    \DDTrace\set_user('usr.id', [
        'name'       => 'usr.name',
        'email'      => 'usr.email',
        'session_id' => 'usr.session_id',
        'role'       => 'usr.role',
        'scope'      => 'usr.scope',
    ], true);
    return response('OK');
});

Route::get('/users', function (Request $request) {
    Auth::user(); // trigger authenticated user tracking for logged-in sessions
    $user = $request->query('user', '');
    \DDTrace\set_user($user, [
        'name'       => 'usr.name',
        'email'      => 'usr.email',
        'session_id' => 'usr.session_id',
        'role'       => 'usr.role',
        'scope'      => 'usr.scope',
    ]);
    return response('OK');
});

Route::match(['GET', 'POST'], '/login', [LoginController::class, 'login']);

Route::post('/signup', [LoginController::class, 'signup']);

Route::get('/user_login_success_event', function (Request $request) {
    \datadog\appsec\track_user_login_success_event(
        $request->query('event_user_id', 'system_tests_user'),
        ['metadata0' => 'value0', 'metadata1' => 'value1']
    );
    return response('OK');
});

Route::get('/user_login_failure_event', function (Request $request) {
    \datadog\appsec\track_user_login_failure_event(
        $request->query('event_user_id', 'system_tests_user'),
        $request->query('event_user_exists', true),
        ['metadata0' => 'value0', 'metadata1' => 'value1']
    );
    return response('OK');
});

Route::get('/custom_event', function (Request $request) {
    \datadog\appsec\track_custom_event(
        $request->query('event_name', 'system_tests_event'),
        ['metadata0' => 'value0', 'metadata1' => 'value1']
    );
    return response('OK');
});

Route::get('/session/new', function () {
    session_start();
    return response(session_id());
});

Route::any('/tag_value/{value}/{status_code}', function (Request $request, string $value, string $statusCode) {
    $rootSpan = \DDTrace\root_span();
    $rootSpan->meta['http.route'] = '/tag_value/{tag_value}/{status_code}';

    \datadog\appsec\push_addresses(['server.request.path_params' => [
        'tag_value'   => $value,
        'status_code' => $statusCode,
    ]]);

    \datadog\appsec\track_custom_event('system_tests_appsec_event', ['value' => $value]);

    foreach ($request->query() as $k => $v) {
        header(ucwords($k) . ': ' . $v);
    }

    $code = is_numeric($statusCode) ? intval($statusCode) : 200;

    $body = 'Value tagged';
    $payloadInResponse = 'payload_in_response_body';
    if (str_starts_with($value, $payloadInResponse) && $request->isMethod('POST')) {
        parse_str($request->getContent(), $parsedRequest);
        return response(sprintf('{"payload": %s }', json_encode($parsedRequest)), $code)
            ->header('Content-Type', 'application/json');
    }

    return response($body, $code);
});

Route::post('/shell_execution', function (Request $request) {
    $spec    = json_decode($request->getContent(), true);
    $command = $spec['command'];
    $options = $spec['options'] ?? [];
    $args    = $spec['args'] ?? [];
    $isShell = !empty($options['shell']);

    if (is_string($args)) {
        $args = preg_split('/\s+/', $args);
    }

    $c = array_merge([$command], $args);
    if ($isShell) {
        $c = implode(' ', $c);
    }

    $p = proc_open($c, [1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
    if (!is_resource($p)) {
        return response('Failed to open process', 500);
    }

    $stdout = stream_get_contents($pipes[1]);
    fclose($pipes[1]);
    $stderr = stream_get_contents($pipes[2]);
    fclose($pipes[2]);

    return response("STDOUT:\n$stdout\nSTDERR:\n$stderr\nexit code: " . proc_close($p) . "\n");
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

    return response('YEAH');
});

Route::get('/returnheaders', function (Request $request) {
    $headers = [];
    foreach ($request->headers->all() as $name => $values) {
        $headers[str_replace(' ', '-', ucwords(str_replace('-', ' ', $name)))] = implode(', ', $values);
    }
    return response()->json($headers);
});
