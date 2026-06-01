<?php

use App\Http\Controllers\LoginController;
use Illuminate\Database\QueryException;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Process;
use Illuminate\Support\Facades\Route;
use Symfony\Component\Process\Exception\RuntimeException as ProcessRuntimeException;

Route::get('/', function () {
    Auth::user();
    return response("Hello world!\n", 200, [
        'Content-Type' => 'text/plain; charset=utf-8',
        'Content-Length' => '13',
    ]);
});

Route::get('/stats-unique', function (Request $request) {
    $code = (int) $request->query('code', 200);
    return response('', $code);
});

Route::get('/sample_rate_route/{i}', function () {
    return response('OK', 200, ['Content-Type' => 'text/plain']);
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

    $requestHeaders = [];
    $response = Http::beforeSending(function ($outgoingRequest) use (&$requestHeaders) {
            foreach ($outgoingRequest->headers() as $name => $values) {
                $requestHeaders[strtolower($name)] = implode(', ', $values);
            }
        })
        ->get($url);

    $responseHeaders = [];
    foreach ($response->headers() as $name => $values) {
        $responseHeaders[strtolower($name)] = implode(', ', $values);
    }

    return response()->json([
        'url'              => $url,
        'status_code'      => $response->status(),
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

    try {
        $result = Process::run($c);
    } catch (ProcessRuntimeException) {
        return response('Failed to open process', 500);
    }

    $out = "STDOUT:\n{$result->output()}\nSTDERR:\n{$result->errorOutput()}\nexit code: {$result->exitCode()}\n";

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
        Log::build([
            'driver' => 'single',
            'path'   => $dir.'/helper.log',
            'level'  => 'debug',
        ])->info('', ['message' => $msg]);
    }

    return response('', 200);
});

Route::match(['GET', 'POST'], '/login', [LoginController::class, 'login']);

Route::post('/signup', [LoginController::class, 'signup']);

Route::post('/user_login_success_event_v2', function (Request $request) {
    $decoded = $request->json()->all();
    $login = $decoded['login'] ?? null;
    $userId = $decoded['user_id'] ?? null;
    $metadata = $decoded['metadata'] ?? null;

    if ($login !== null && $userId !== null && $metadata !== null) {
        \datadog\appsec\v2\track_user_login_success($login, $userId, $metadata);
    } elseif ($login !== null && $userId !== null) {
        \datadog\appsec\v2\track_user_login_success($login, $userId);
    } else {
        \datadog\appsec\v2\track_user_login_success($login);
    }

    return response('OK', 200, ['Content-Type' => 'text/plain']);
});

Route::post('/user_login_failure_event_v2', function (Request $request) {
    $decoded = $request->json()->all();
    $login = $decoded['login'] ?? null;
    $exists = isset($decoded['exists']) ? ($decoded['exists'] === 'true' || $decoded['exists'] === true) : null;
    $metadata = $decoded['metadata'] ?? null;

    if ($login !== null && $exists !== null && $metadata !== null) {
        \datadog\appsec\v2\track_user_login_failure($login, $exists, $metadata);
    } elseif ($login !== null && $exists !== null) {
        \datadog\appsec\v2\track_user_login_failure($login, $exists);
    } else {
        \datadog\appsec\v2\track_user_login_failure($login);
    }

    return response('OK', 200, ['Content-Type' => 'text/plain']);
});

Route::match(['get', 'post'], '/rasp/lfi', function (Request $request) {
    $file = null;
    $contentType = $request->header('Content-Type', '');
    if ($contentType === 'application/json') {
        $decoded = json_decode($request->getContent(), true);
        $file = $decoded['file'] ?? '';
    } elseif ($contentType === 'application/xml') {
        $decoded = simplexml_load_string(stripslashes($request->getContent()));
        $file = (string) ($decoded[0] ?? '');
    } else {
        $file = urldecode($request->input('file', ''));
    }
    @file_get_contents($file);

    return response('Hello, LFI!', 200, ['Content-Type' => 'text/plain']);
});

Route::match(['get', 'post'], '/rasp/ssrf', function (Request $request) {
    $domain = null;
    $contentType = $request->header('Content-Type', '');
    if ($contentType === 'application/json') {
        $decoded = json_decode($request->getContent(), true);
        $domain = $decoded['domain'] ?? '';
    } elseif ($contentType === 'application/xml') {
        $decoded = simplexml_load_string(stripslashes($request->getContent()));
        $domain = (string) ($decoded[0] ?? '');
    } else {
        $domain = urldecode($request->input('domain', ''));
    }
    @file_get_contents('http://'.$domain);

    return response('Hello, SSRF!', 200, ['Content-Type' => 'text/plain']);
});

Route::get('/rasp/multiple', function (Request $request) {
    @file_get_contents(urldecode($request->query('file1', '')));
    @file_get_contents(urldecode($request->query('file2', '')));
    @file_get_contents('../etc/passwd');

    return response('Hello, multiple rasp!', 200, ['Content-Type' => 'text/plain']);
});

Route::get('/db', function (Request $request) {
    $service = $request->query('service', '');
    $operation = $request->query('operation', '');

    $mysqlOp = static function (string $op): void {
        $db = DB::connection('mysql');
        switch ($op) {
            case 'init':
                $db->statement('CREATE TABLE IF NOT EXISTS demo(id INT NOT NULL, name VARCHAR(20) NOT NULL, age INT NOT NULL, PRIMARY KEY (id))');
                $db->statement("INSERT IGNORE INTO demo (id, name, age) VALUES (1, 'test', 16)");
                $db->statement("INSERT IGNORE INTO demo (id, name, age) VALUES (2, 'test2', 17)");
                $db->statement('DROP PROCEDURE IF EXISTS test_procedure');
                $db->unprepared('CREATE PROCEDURE test_procedure(IN test_id INT, IN other VARCHAR(20))
BEGIN
    SELECT demo.id, demo.name, demo.age FROM demo WHERE demo.id = test_id;
END');
                break;
            case 'select':
                $db->select('SELECT * from demo where id=1 or id IN (3, 4)');
                break;
            case 'insert':
                try {
                    $db->statement("insert into demo (id, name, age) values(3, 'test3', 163)");
                } catch (QueryException $e) {}
                break;
            case 'update':
                $db->statement('update demo set age=22 where id=1');
                break;
            case 'delete':
                $db->statement('delete from demo where id=2 or id=11111111');
                break;
            case 'procedure':
                $db->statement("call test_procedure(1, 'test')");
                break;
            case 'select_error':
                try {
                    $db->select('SELECT * from demosssss where id=1 or id=233333');
                } catch (QueryException $e) {}
                break;
        }
    };

    $postgresOp = static function (string $op): void {
        $db = DB::connection('postgresql');
        switch ($op) {
            case 'init':
                try {
                    $db->statement('CREATE TABLE demo(id INT NOT NULL, name VARCHAR(20) NOT NULL, age INT NOT NULL, PRIMARY KEY (id))');
                } catch (QueryException $e) {}
                try {
                    $db->statement("INSERT INTO demo (id, name, age) VALUES (1, 'test', 16)");
                } catch (QueryException $e) {}
                try {
                    $db->statement("INSERT INTO demo (id, name, age) VALUES (2, 'test2', 17)");
                } catch (QueryException $e) {}
                $db->unprepared("CREATE OR REPLACE PROCEDURE helloworld(id int, other varchar(10))
LANGUAGE plpgsql
AS \$\$
BEGIN
    raise info 'Hello World';
END;
\$\$");
                break;
            case 'select':
                $db->select('SELECT * from demo where id=1 or id IN (3, 4)');
                break;
            case 'insert':
                try {
                    $db->statement("insert into demo (id, name, age) values(3, 'test3', 163)");
                } catch (QueryException $e) {}
                break;
            case 'update':
                $db->statement("update demo set age=22 where name like '%tes%'");
                break;
            case 'delete':
                $db->statement('delete from demo where id=2 or id=11111111');
                break;
            case 'procedure':
                $db->statement("call helloworld(1, 'test')");
                break;
            case 'select_error':
                try {
                    $db->select('SELECT * from demosssssssss where id=1 or id=233333');
                } catch (QueryException $e) {}
                break;
        }
    };

    if ($service === 'mysql') {
        $mysqlOp($operation);
    } elseif ($service === 'postgresql') {
        $postgresOp($operation);
    } else {
        return response('Unsupported service: '.htmlspecialchars($service), 400, ['Content-Type' => 'text/plain']);
    }

    return response('YEAH', 200, ['Content-Type' => 'text/plain']);
});

Route::get('/trace/sql', function () {

    try {
        $pdo = new PDO("mysql:dbname=mysql_dbname;host=mysqldb", "mysqldb", "mysqldb");
        $pdo->query("SELECT 1");
    } catch (\Exception $e) {
        // Ignore connection issues
    }

    return response('OK', 200, ['Content-Type' => 'text/plain']);
});

Route::get('/endpoint_fallback.php', function (Request $request) {
    $rootSpan = \DDTrace\root_span();
    $case = $request->query('case', 'unknown');

    switch ($case) {
        case 'with_route':
            $rootSpan->meta['http.route'] = '/users/{id}/profile';
            $rootSpan->meta['http.method'] = 'GET';

            return response()->json([
                'status'    => 'ok',
                'test_case' => 'with_route',
                'message'   => 'http.route is set',
            ]);

        case 'with_endpoint':
            unset($rootSpan->meta['http.route']);
            $rootSpan->meta['http.endpoint'] = '/api/products/{param:int}';
            $rootSpan->meta['http.method'] = 'GET';

            return response()->json([
                'status'    => 'ok',
                'test_case' => 'with_endpoint',
                'message'   => 'http.endpoint is set, http.route is not',
            ]);

        case '404':
            unset($rootSpan->meta['http.route']);
            $rootSpan->meta['http.endpoint'] = '/api/notfound/{param:int}';
            $rootSpan->meta['http.method'] = 'GET';

            return response()->json([
                'status'    => 'error',
                'test_case' => '404_with_endpoint',
                'message'   => 'Not found - should not sample despite http.endpoint',
            ], 404);

        case 'computed':
            unset($rootSpan->meta['http.route']);
            $rootSpan->meta['http.url'] = 'http://localhost:8080/endpoint_fallback_computed/users/123/orders/456';
            $rootSpan->meta['http.method'] = 'GET';

            return response()->json([
                'status'           => 'ok',
                'test_case'        => 'computed_on_demand',
                'message'          => 'Endpoint computed from URL',
                'has_endpoint_tag' => isset($rootSpan->meta['http.endpoint']),
            ]);

        default:
            return response()->json([
                'status'    => 'error',
                'test_case' => 'unknown',
                'message'   => 'Invalid case parameter. Valid values: with_route, with_endpoint, 404, computed',
            ], 400);
    }
});

Route::get('/api_security_sampling/{id}', function (Request $request, string $id) {
    // $rootSpan = \DDTrace\root_span();
    // $rootSpan->meta['http.route'] = '/api_security_sampling/{id}';

    return response()->json(['status' => 200], 200);
});

Route::get('/api_security/sampling/{status}', function (Request $request, string $status) {
    // $rootSpan = \DDTrace\root_span();
    // $rootSpan->meta['http.route'] = '/api_security/sampling/{status}';
    $statusCode = intval($status);
    if ($statusCode >= 200 && $statusCode <= 599) {
        return response()->json(['status' => $statusCode], $statusCode);
    }

    return response('Invalid status', 400, ['Content-Type' => 'text/plain']);
});

Route::get('/otel_drop_in_baggage_api_otel', function (Request $request) {
    $url = $request->query('url');
    if ($url === null) {
        return response()->json(['error' => 'Specify the url to call in the query string'], 400);
    }

    $baggage = \OpenTelemetry\API\Baggage\Baggage::getCurrent();
    $builder = $baggage->toBuilder();

    $baggageRemove = $request->query('baggage_remove');
    if ($baggageRemove !== null) {
        foreach (explode(',', $baggageRemove) as $key) {
            $builder = $builder->remove(trim($key));
        }
    }

    $baggageSet = $request->query('baggage_set');
    if ($baggageSet !== null) {
        foreach (explode(',', $baggageSet) as $item) {
            $parts = explode('=', $item, 2);
            if (count($parts) === 2) {
                $builder = $builder->set(trim($parts[0]), trim($parts[1]));
            }
        }
    }

    $scope = null;
    try {
        $scope = $builder->build()->activate();

        $responseHeaders = [];
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_HEADER, false);
        curl_setopt($ch, CURLINFO_HEADER_OUT, true);
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
                    $requestHeaders[trim($key)] = trim($value);
                }
            }
        }
        curl_close($ch);
    } finally {
        if ($scope !== null) {
            $scope->detach();
        }
    }

    return response()->json([
        'url'              => $url,
        'status_code'      => $statusCode,
        'request_headers'  => $requestHeaders,
        'response_headers' => $responseHeaders,
    ]);
});

Route::get('/otel_drop_in_baggage_api_datadog', function (Request $request) {
    $url = $request->query('url');
    if ($url === null) {
        return response()->json(['error' => 'Specify the url to call in the query string'], 400);
    }

    $span = \DDTrace\root_span();
    if ($span !== null) {
        $baggageRemove = $request->query('baggage_remove');
        if ($baggageRemove !== null) {
            foreach (explode(',', $baggageRemove) as $key) {
                unset($span->baggage[trim($key)]);
            }
        }

        $baggageSet = $request->query('baggage_set');
        if ($baggageSet !== null) {
            foreach (explode(',', $baggageSet) as $item) {
                $parts = explode('=', $item, 2);
                if (count($parts) === 2) {
                    $span->baggage[trim($parts[0])] = trim($parts[1]);
                }
            }
        }
    }

    $responseHeaders = [];
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HEADER, false);
    curl_setopt($ch, CURLINFO_HEADER_OUT, true);
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
                $requestHeaders[trim($key)] = trim($value);
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
Route::get('/returnheaders', function (Request $request) {
    $headers = [];
    foreach ($request->headers->all() as $key => $values) {
        $headers[$key] = implode(', ', $values);
    }

    return response()->json($headers);
});

Route::get('/requestdownstream', function (Request $request) {
    $ch = curl_init('http://127.0.0.1:7777/returnheaders');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    $body = curl_exec($ch);
    curl_close($ch);

    return response($body, 200, ['Content-Type' => 'application/json']);
});

Route::get('/load_dependency', function () {
    $acme = new \Acme\Acme();
    return response('ok', 200, ['Content-Type' => 'text/plain']);
});
