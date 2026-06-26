<?php

namespace App\Controller;

use Monolog\Handler\StreamHandler;
use Monolog\Logger;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpClient\HttpClient;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Process\Exception\RuntimeException as ProcessRuntimeException;
use Symfony\Component\Process\Process;
use Symfony\Component\Routing\Attribute\Route;

class AppController extends AbstractController
{
    #[Route('/', name: 'index', methods: ['GET'])]
    public function index(): Response
    {
        $this->getUser();

        return new Response("Hello world!\n", 200, [
            'Content-Type'   => 'text/plain; charset=utf-8',
            'Content-Length' => '13',
        ]);
    }

    #[Route('/stats-unique', name: 'stats_unique', methods: ['GET'])]
    public function statsUnique(Request $request): Response
    {
        $code = (int) $request->query->get('code', 200);

        return new Response('', $code);
    }

    #[Route('/sample_rate_route/{i}', name: 'sample_rate_route', methods: ['GET'])]
    public function sampleRateRoute(): Response
    {
        return new Response('OK', 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/healthcheck', name: 'healthcheck', methods: ['GET'])]
    public function healthcheck(): JsonResponse
    {
        $version = phpversion('ddtrace') ?: 'unknown';

        return new JsonResponse([
            'status'  => 'ok',
            'library' => ['name' => 'php', 'version' => $version],
        ]);
    }

    #[Route('/status', name: 'status', methods: ['GET'])]
    public function status(Request $request): Response
    {
        $code = intval($request->query->get('code', 200));

        return new Response('', $code);
    }

    #[Route('/make_distant_call', name: 'make_distant_call', methods: ['GET'])]
    public function makeDistantCall(Request $request): JsonResponse
    {
        $url = $request->query->get('url', '');
        if ($url === '') {
            return new JsonResponse(['error' => 'url parameter required'], 400);
        }

        $client   = HttpClient::create();
        $response = $client->request('GET', $url);

        $statusCode      = $response->getStatusCode();
        $responseHeaders = [];
        foreach ($response->getHeaders(false) as $name => $values) {
            $responseHeaders[$name] = implode(', ', $values);
        }
        $requestHeaders = $this->parseRequestHeadersFromDebug($response->getInfo('debug') ?? '');

        return new JsonResponse([
            'url'              => $url,
            'status_code'      => $statusCode,
            'request_headers'  => $requestHeaders,
            'response_headers' => $responseHeaders,
        ]);
    }

    #[Route('/read_file', name: 'read_file', methods: ['GET'])]
    public function readFile(Request $request): Response
    {
        $file    = $request->query->get('file', '');
        $content = @file_get_contents($file);

        return new Response($content === false ? '' : $content, 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/users', name: 'users', methods: ['GET'])]
    public function users(Request $request): Response
    {
        $user = $request->query->get('user');

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

        return new Response('OK', 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/identify', name: 'identify', methods: ['GET'])]
    public function identify(): Response
    {
        \DDTrace\set_user('usr.id', [
            'name'       => 'usr.name',
            'email'      => 'usr.email',
            'session_id' => 'usr.session_id',
            'role'       => 'usr.role',
            'scope'      => 'usr.scope',
        ]);

        return new Response('', 200);
    }

    #[Route('/identify-propagate', name: 'identify_propagate', methods: ['GET'])]
    public function identifyPropagate(): Response
    {
        \DDTrace\set_user('usr.id', [
            'name'       => 'usr.name',
            'email'      => 'usr.email',
            'session_id' => 'usr.session_id',
            'role'       => 'usr.role',
            'scope'      => 'usr.scope',
        ], true);

        return new Response('', 200);
    }

    #[Route('/waf', name: 'waf', methods: ['GET', 'POST'])]
    public function waf(): Response
    {
        return new Response('Hello, WAF!', 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/waf/{path}', name: 'waf_path', requirements: ['path' => '.*'], methods: ['GET', 'POST'])]
    public function wafPath(): Response
    {
        return new Response('Hello, WAF!', 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/headers', name: 'headers', methods: ['GET'])]
    public function headers(): Response
    {
        return new Response('Hello, headers!', 200, [
            'Content-Type'     => 'text/plain',
            'Content-Length'   => '15',
            'Content-Language' => 'en-US',
        ]);
    }

    #[Route('/session/new', name: 'session_new', methods: ['GET'])]
    public function sessionNew(Request $request): Response
    {
        $session = $request->getSession();
        $session->start();

        return new Response($session->getId(), 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/user_login_success_event', name: 'user_login_success_event', methods: ['GET'])]
    public function userLoginSuccessEvent(Request $request): Response
    {
        \datadog\appsec\track_user_login_success_event($request->query->get('event_user_id', 'system_tests_user'), [
            'metadata0' => 'value0',
            'metadata1' => 'value1',
        ]);

        return new Response('', 200);
    }

    #[Route('/user_login_failure_event', name: 'user_login_failure_event', methods: ['GET'])]
    public function userLoginFailureEvent(Request $request): Response
    {
        $exists     = $request->query->get('event_user_exists', 'true');
        $existsBool = filter_var($exists, FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE);
        if ($existsBool === null) {
            $existsBool = true;
        }

        \datadog\appsec\track_user_login_failure_event(
            $request->query->get('event_user_id', 'system_tests_user'),
            $existsBool,
            [
                'metadata0' => 'value0',
                'metadata1' => 'value1',
            ]
        );

        return new Response('', 200);
    }

    #[Route('/custom_event', name: 'custom_event', methods: ['GET'])]
    public function customEvent(Request $request): Response
    {
        \datadog\appsec\track_custom_event($request->query->get('event_name', 'system_tests_event'), [
            'metadata0' => 'value0',
            'metadata1' => 'value1',
        ]);

        return new Response('', 200);
    }

    #[Route('/shell_execution', name: 'shell_execution', methods: ['POST'])]
    public function shellExecution(Request $request): Response
    {
        $spec    = json_decode($request->getContent(), true) ?: [];
        $command = $spec['command'] ?? '';
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

        try {
            $process = $isShell ? Process::fromShellCommandline($c) : new Process($c);
            $process->run();
        } catch (ProcessRuntimeException) {
            return new Response('Failed to open process', 500);
        }

        $out = "STDOUT:\n{$process->getOutput()}\nSTDERR:\n{$process->getErrorOutput()}\nexit code: {$process->getExitCode()}\n";

        return new Response($out, 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/tag_value/{tag_value}/{status_code}', name: 'tag_value', methods: ['GET', 'POST', 'OPTIONS'])]
    public function tagValue(string $tag_value, string $status_code, Request $request): Response
    {
        $responseCodeStr = strtok($status_code, '?') ?: $status_code;
        if (!is_numeric($responseCodeStr)) {
            return new Response('Error parsing uri', 400);
        }
        $responseCode = (int) $responseCodeStr;
        \datadog\appsec\track_custom_event('system_tests_appsec_event', [
            'value' => $tag_value,
        ]);
        foreach ($request->query->all() as $key => $value) {
            header(ucwords($key) . ': ' . $value);
        }
        $body          = 'Value tagged';
        $payloadPrefix = 'payload_in_response_body';
        if (str_starts_with($tag_value, $payloadPrefix) && $request->isMethod('POST')) {
            $parsed = $request->request->all() ?: (json_decode($request->getContent(), true) ?? []);

            return new JsonResponse(['payload' => $parsed], $responseCode === 200 ? 200 : $responseCode);
        }
        if ($responseCode !== 200) {
            return new Response($body, $responseCode, ['Content-Type' => 'text/plain']);
        }

        return new Response($body, 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/params/{param}', name: 'params', methods: ['GET'])]
    public function params(): Response
    {
        return new Response('ok', 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/dbm', name: 'dbm', methods: ['GET'])]
    public function dbm(Request $request): Response
    {
        $integration = $request->query->get('integration', '');
        $query       = 'SELECT version()';

        if ($integration === 'pdo-mysql') {
            $connection = new \PDO('mysql:dbname=mysql_dbname;host=mysqldb', 'mysqldb', 'mysqldb');
            $connection->query($query);
        } elseif ($integration === 'pdo-pgsql') {
            $connection = new \PDO('pgsql:dbname=system_tests_dbname;host=postgres;port=5433', 'system_tests_user', 'system_tests');
            $connection->query($query);
        } elseif ($integration === 'mysqli') {
            $connection = new \mysqli('mysqldb', 'mysqldb', 'mysqldb', 'mysql_dbname');
            $connection->query($query);
        }

        return new Response('', 200);
    }

    #[Route('/log/library', name: 'log_library', methods: ['GET'])]
    public function logLibrary(Request $request): Response
    {
        $dir = $_ENV['SYSTEM_TESTS_LOGS'] ?? '/var/log/system-tests';
        if (!is_dir($dir)) {
            @mkdir($dir, 0777, true);
        }
        $msg = $request->query->get('msg', '');
        if ($msg !== '') {
            $logger = new Logger('system_tests');
            $logger->pushHandler(new StreamHandler($dir . '/helper.log', Logger::DEBUG));
            $logger->info('', ['message' => $msg]);
        }

        return new Response('', 200);
    }

    #[Route('/user_login_success_event_v2', name: 'user_login_success_event_v2', methods: ['POST'])]
    public function userLoginSuccessEventV2(Request $request): Response
    {
        $decoded  = json_decode($request->getContent(), true) ?: [];
        $login    = $decoded['login'] ?? null;
        $userId   = $decoded['user_id'] ?? null;
        $metadata = $decoded['metadata'] ?? null;

        if ($login !== null && $userId !== null && $metadata !== null) {
            \datadog\appsec\v2\track_user_login_success($login, $userId, $metadata);
        } elseif ($login !== null && $userId !== null) {
            \datadog\appsec\v2\track_user_login_success($login, $userId);
        } else {
            \datadog\appsec\v2\track_user_login_success($login);
        }

        return new Response('OK', 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/user_login_failure_event_v2', name: 'user_login_failure_event_v2', methods: ['POST'])]
    public function userLoginFailureEventV2(Request $request): Response
    {
        $decoded  = json_decode($request->getContent(), true) ?: [];
        $login    = $decoded['login'] ?? null;
        $exists   = isset($decoded['exists']) ? ($decoded['exists'] === 'true' || $decoded['exists'] === true) : null;
        $metadata = $decoded['metadata'] ?? null;

        if ($login !== null && $exists !== null && $metadata !== null) {
            \datadog\appsec\v2\track_user_login_failure($login, $exists, $metadata);
        } elseif ($login !== null && $exists !== null) {
            \datadog\appsec\v2\track_user_login_failure($login, $exists);
        } else {
            \datadog\appsec\v2\track_user_login_failure($login);
        }

        return new Response('OK', 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/stub_dbm', name: 'stub_dbm', methods: ['GET'])]
    public function stubDbm(Request $request): JsonResponse
    {
        $integration = $request->query->get('integration', '');
        $stmt        = null;

        if ($integration === 'pdo-pgsql') {
            $con  = new \PDO('pgsql:dbname=system_tests_dbname;host=postgres;port=5433', 'system_tests_user', 'system_tests');
            $stmt = $con->query('SELECT version()');
        } elseif ($integration === 'pdo-mysql') {
            $con  = new \PDO('mysql:dbname=mysql_dbname;host=mysqldb', 'mysqldb', 'mysqldb');
            $stmt = $con->query('SELECT version()');
        }

        $captured = $stmt instanceof \PDOStatement ? $stmt->queryString : null;

        return new JsonResponse([
            'status'      => 'ok',
            'dbm_comment' => $captured,
        ]);
    }

    #[Route('/rasp/sqli', name: 'rasp_sqli', methods: ['GET', 'POST'])]
    public function raspSqli(Request $request): Response
    {
        $userId      = null;
        $contentType = $request->headers->get('Content-Type', '');
        if ($contentType === 'application/json') {
            $decoded = json_decode($request->getContent(), true);
            $userId  = $decoded['user_id'] ?? '';
        } elseif ($contentType === 'application/xml') {
            $decoded = simplexml_load_string(stripslashes($request->getContent()));
            $userId  = (string) ($decoded[0] ?? '');
        } else {
            $userId = urldecode($request->get('user_id', ''));
        }

        // Use SQLite (always available) for RASP SQL injection detection
        $dbPath = getenv('SYMFONY_DB_PATH') ?: '/tmp/symfony.db';
        $pdo    = new \PDO("sqlite:$dbPath");
        // Intentionally unsafe query so ddtrace RASP can detect the injection
        @$pdo->query("SELECT * FROM users WHERE id = '" . $userId . "'");

        return new Response('Hello, SQLi!', 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/rasp/lfi', name: 'rasp_lfi', methods: ['GET', 'POST'])]
    public function raspLfi(Request $request): Response
    {
        $file        = null;
        $contentType = $request->headers->get('Content-Type', '');
        if ($contentType === 'application/json') {
            $decoded = json_decode($request->getContent(), true);
            $file    = $decoded['file'] ?? '';
        } elseif ($contentType === 'application/xml') {
            $decoded = simplexml_load_string(stripslashes($request->getContent()));
            $file    = (string) ($decoded[0] ?? '');
        } else {
            $file = urldecode($request->get('file', ''));
        }
        @file_get_contents($file);

        return new Response('Hello, LFI!', 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/rasp/ssrf', name: 'rasp_ssrf', methods: ['GET', 'POST'])]
    public function raspSsrf(Request $request): Response
    {
        $domain      = null;
        $contentType = $request->headers->get('Content-Type', '');
        if ($contentType === 'application/json') {
            $decoded = json_decode($request->getContent(), true);
            $domain  = $decoded['domain'] ?? '';
        } elseif ($contentType === 'application/xml') {
            $decoded = simplexml_load_string(stripslashes($request->getContent()));
            $domain  = (string) ($decoded[0] ?? '');
        } else {
            $domain = urldecode($request->get('domain', ''));
        }
        @file_get_contents('http://' . $domain);

        return new Response('Hello, SSRF!', 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/rasp/multiple', name: 'rasp_multiple', methods: ['GET'])]
    public function raspMultiple(Request $request): Response
    {
        @file_get_contents(urldecode($request->query->get('file1', '')));
        @file_get_contents(urldecode($request->query->get('file2', '')));
        @file_get_contents('../etc/passwd');

        return new Response('Hello, multiple rasp!', 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/db', name: 'db', methods: ['GET'])]
    public function db(Request $request): Response
    {
        $service   = $request->query->get('service', '');
        $operation = $request->query->get('operation', '');

        $mysqlOp = static function (string $op): void {
            $db = new \PDO('mysql:dbname=mysql_dbname;host=mysqldb', 'mysqldb', 'mysqldb');
            switch ($op) {
                case 'init':
                    $db->exec('CREATE TABLE IF NOT EXISTS demo(id INT NOT NULL, name VARCHAR(20) NOT NULL, age INT NOT NULL, PRIMARY KEY (id))');
                    $db->exec("INSERT IGNORE INTO demo (id, name, age) VALUES (1, 'test', 16)");
                    $db->exec("INSERT IGNORE INTO demo (id, name, age) VALUES (2, 'test2', 17)");
                    $db->exec('DROP PROCEDURE IF EXISTS test_procedure');
                    $db->exec('CREATE PROCEDURE test_procedure(IN test_id INT, IN other VARCHAR(20))
BEGIN
    SELECT demo.id, demo.name, demo.age FROM demo WHERE demo.id = test_id;
END');
                    break;
                case 'select':
                    $db->query('SELECT * from demo where id=1 or id IN (3, 4)');
                    break;
                case 'insert':
                    try {
                        $db->exec("insert into demo (id, name, age) values(3, 'test3', 163)");
                    } catch (\PDOException $e) {}
                    break;
                case 'update':
                    $db->exec('update demo set age=22 where id=1');
                    break;
                case 'delete':
                    $db->exec('delete from demo where id=2 or id=11111111');
                    break;
                case 'procedure':
                    $db->exec("call test_procedure(1, 'test')");
                    break;
                case 'select_error':
                    try {
                        $db->query('SELECT * from demosssss where id=1 or id=233333');
                    } catch (\PDOException $e) {}
                    break;
            }
        };

        $postgresOp = static function (string $op): void {
            $db = new \PDO('pgsql:dbname=system_tests_dbname;host=postgres;port=5433', 'system_tests_user', 'system_tests');
            switch ($op) {
                case 'init':
                    try {
                        $db->exec('CREATE TABLE demo(id INT NOT NULL, name VARCHAR(20) NOT NULL, age INT NOT NULL, PRIMARY KEY (id))');
                    } catch (\PDOException $e) {}
                    try {
                        $db->exec("INSERT INTO demo (id, name, age) VALUES (1, 'test', 16)");
                    } catch (\PDOException $e) {}
                    try {
                        $db->exec("INSERT INTO demo (id, name, age) VALUES (2, 'test2', 17)");
                    } catch (\PDOException $e) {}
                    $db->exec("CREATE OR REPLACE PROCEDURE helloworld(id int, other varchar(10))
LANGUAGE plpgsql
AS \$\$
BEGIN
    raise info 'Hello World';
END;
\$\$");
                    break;
                case 'select':
                    $db->query('SELECT * from demo where id=1 or id IN (3, 4)');
                    break;
                case 'insert':
                    try {
                        $db->exec("insert into demo (id, name, age) values(3, 'test3', 163)");
                    } catch (\PDOException $e) {}
                    break;
                case 'update':
                    $db->exec("update demo set age=22 where name like '%tes%'");
                    break;
                case 'delete':
                    $db->exec('delete from demo where id=2 or id=11111111');
                    break;
                case 'procedure':
                    $db->exec("call helloworld(1, 'test')");
                    break;
                case 'select_error':
                    try {
                        $db->query('SELECT * from demosssssssss where id=1 or id=233333');
                    } catch (\PDOException $e) {}
                    break;
            }
        };

        if ($service === 'mysql') {
            $mysqlOp($operation);
        } elseif ($service === 'postgresql') {
            $postgresOp($operation);
        } else {
            return new Response('Unsupported service: ' . htmlspecialchars($service), 400, ['Content-Type' => 'text/plain']);
        }

        return new Response('YEAH', 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/trace/sql', name: 'trace_sql', methods: ['GET'])]
    public function traceSql(): Response
    {
        try {
            $pdo = new \PDO('mysql:dbname=mysql_dbname;host=mysqldb', 'mysqldb', 'mysqldb');
            $pdo->query('SELECT 1');
        } catch (\Exception $e) {}

        return new Response('OK', 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/endpoint_fallback.php', name: 'endpoint_fallback', methods: ['GET'])]
    public function endpointFallback(Request $request): JsonResponse
    {
        $rootSpan = \DDTrace\root_span();
        $case     = $request->query->get('case', 'unknown');

        switch ($case) {
            case 'with_route':
                register_shutdown_function(function () use ($rootSpan): void {
                    $rootSpan->meta['http.route']  = '/users/{id}/profile';
                    $rootSpan->meta['http.method'] = 'GET';
                });

                return new JsonResponse([
                    'status'    => 'ok',
                    'test_case' => 'with_route',
                    'message'   => 'http.route is set',
                ]);

            case 'with_endpoint':
                register_shutdown_function(function () use ($rootSpan): void {
                    unset($rootSpan->meta['http.route']);
                    $rootSpan->meta['http.endpoint'] = '/api/products/{param:int}';
                    $rootSpan->meta['http.method']   = 'GET';
                });

                return new JsonResponse([
                    'status'    => 'ok',
                    'test_case' => 'with_endpoint',
                    'message'   => 'http.endpoint is set, http.route is not',
                ]);

            case '404':
                register_shutdown_function(function () use ($rootSpan): void {
                    unset($rootSpan->meta['http.route']);
                    $rootSpan->meta['http.endpoint'] = '/api/notfound/{param:int}';
                    $rootSpan->meta['http.method']   = 'GET';
                });

                return new JsonResponse([
                    'status'    => 'error',
                    'test_case' => '404_with_endpoint',
                    'message'   => 'Not found - should not sample despite http.endpoint',
                ], 404);

            case 'computed':
                register_shutdown_function(function () use ($rootSpan): void {
                    unset($rootSpan->meta['http.route']);
                    $rootSpan->meta['http.url']    = 'http://localhost:8080/endpoint_fallback_computed/users/123/orders/456';
                    $rootSpan->meta['http.method'] = 'GET';
                });

                return new JsonResponse([
                    'status'           => 'ok',
                    'test_case'        => 'computed_on_demand',
                    'message'          => 'Endpoint computed from URL',
                    'has_endpoint_tag' => isset($rootSpan->meta['http.endpoint']),
                ]);

            default:
                return new JsonResponse([
                    'status'    => 'error',
                    'test_case' => 'unknown',
                    'message'   => 'Invalid case parameter. Valid values: with_route, with_endpoint, 404, computed',
                ], 400);
        }
    }

    #[Route('/api_security_sampling/{id}', name: 'api_security_sampling', methods: ['GET'])]
    public function apiSecuritySampling(string $id): JsonResponse
    {
        return new JsonResponse(['status' => 200], 200);
    }

    #[Route('/api_security/sampling/{status}', name: 'api_security_sampling_status', methods: ['GET'])]
    public function apiSecuritySamplingStatus(string $status): Response
    {
        $statusCode = intval($status);
        if ($statusCode >= 200 && $statusCode <= 599) {
            return new JsonResponse(['status' => $statusCode], $statusCode);
        }

        return new Response('Invalid status', 400, ['Content-Type' => 'text/plain']);
    }

    #[Route('/otel_drop_in_baggage_api_otel', name: 'otel_drop_in_baggage_api_otel', methods: ['GET'])]
    public function otelDropInBaggageApiOtel(Request $request): JsonResponse
    {
        $url = $request->query->get('url');
        if ($url === null) {
            return new JsonResponse(['error' => 'Specify the url to call in the query string'], 400);
        }

        $baggage = \OpenTelemetry\API\Baggage\Baggage::getCurrent();
        $builder = $baggage->toBuilder();

        $baggageRemove = $request->query->get('baggage_remove');
        if ($baggageRemove !== null) {
            foreach (explode(',', $baggageRemove) as $key) {
                $builder = $builder->remove(trim($key));
            }
        }

        $baggageSet = $request->query->get('baggage_set');
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
            $scope          = $builder->build()->activate();
            $client         = HttpClient::create();
            $response       = $client->request('GET', $url);
            $statusCode     = $response->getStatusCode();
            $responseHeaders = [];
            foreach ($response->getHeaders(false) as $name => $values) {
                $responseHeaders[$name] = implode(', ', $values);
            }
            $requestHeaders = $this->parseRequestHeadersFromDebug($response->getInfo('debug') ?? '');
        } finally {
            if ($scope !== null) {
                $scope->detach();
            }
        }

        return new JsonResponse([
            'url'              => $url,
            'status_code'      => $statusCode,
            'request_headers'  => $requestHeaders,
            'response_headers' => $responseHeaders,
        ]);
    }

    #[Route('/otel_drop_in_baggage_api_datadog', name: 'otel_drop_in_baggage_api_datadog', methods: ['GET'])]
    public function otelDropInBaggageApiDatadog(Request $request): JsonResponse
    {
        $url = $request->query->get('url');
        if ($url === null) {
            return new JsonResponse(['error' => 'Specify the url to call in the query string'], 400);
        }

        $span = \DDTrace\root_span();
        if ($span !== null) {
            $baggageRemove = $request->query->get('baggage_remove');
            if ($baggageRemove !== null) {
                foreach (explode(',', $baggageRemove) as $key) {
                    unset($span->baggage[trim($key)]);
                }
            }

            $baggageSet = $request->query->get('baggage_set');
            if ($baggageSet !== null) {
                foreach (explode(',', $baggageSet) as $item) {
                    $parts = explode('=', $item, 2);
                    if (count($parts) === 2) {
                        $span->baggage[trim($parts[0])] = trim($parts[1]);
                    }
                }
            }
        }

        $client          = HttpClient::create();
        $response        = $client->request('GET', $url);
        $statusCode      = $response->getStatusCode();
        $responseHeaders = [];
        foreach ($response->getHeaders(false) as $name => $values) {
            $responseHeaders[$name] = implode(', ', $values);
        }
        $requestHeaders = $this->parseRequestHeadersFromDebug($response->getInfo('debug') ?? '');

        return new JsonResponse([
            'url'              => $url,
            'status_code'      => $statusCode,
            'request_headers'  => $requestHeaders,
            'response_headers' => $responseHeaders,
        ]);
    }

    private function parseRequestHeadersFromDebug(string $debug): array
    {
        $headers    = [];
        $inRequest  = false;
        foreach (explode("\n", $debug) as $line) {
            $line = rtrim($line);
            if (str_starts_with($line, '> ')) {
                $inRequest = true;
                $line      = substr($line, 2);
            } elseif ($inRequest && str_starts_with($line, '< ')) {
                break;
            } elseif ($inRequest && $line === '') {
                break;
            }
            if ($inRequest && str_contains($line, ':')) {
                [$key, $value]                    = explode(':', $line, 2);
                $headers[strtolower(trim($key))] = trim($value);
            }
        }

        return $headers;
    }

    #[Route('/returnheaders', name: 'returnheaders', methods: ['GET'])]
    public function returnHeaders(Request $request): JsonResponse
    {
        $headers = [];
        foreach ($request->headers->all() as $key => $values) {
            $headers[$key] = implode(', ', $values);
        }

        return new JsonResponse($headers);
    }

    #[Route('/requestdownstream', name: 'requestdownstream', methods: ['GET'])]
    public function requestDownstream(): Response
    {
        $client   = HttpClient::create();
        $response = $client->request('GET', 'http://127.0.0.1:7777/returnheaders');
        $body     = $response->getContent(false);

        return new Response($body, 200, ['Content-Type' => 'application/json']);
    }

    #[Route('/load_dependency', name: 'load_dependency', methods: ['GET'])]
    public function loadDependency(): Response
    {
        $acme = new \Acme\Acme();

        return new Response('ok', 200, ['Content-Type' => 'text/plain']);
    }

    #[Route('/stripe/webhook', name: 'stripe_webhook', methods: ['POST'])]
    public function stripeWebhook(Request $request): JsonResponse
    {
        try {
            \Stripe\Stripe::setApiKey('sk_FAKE');
            \Stripe\Stripe::$apiBase = 'http://internal_server:8089';

            $payload   = $request->getContent();
            $sigHeader = $request->headers->get('Stripe-Signature', '');
            $event     = \Stripe\Webhook::constructEvent($payload, $sigHeader, 'whsec_FAKE');

            return new JsonResponse($event->data->object->toArray());
        } catch (\Stripe\Exception\SignatureVerificationException $e) {
            return new JsonResponse(['error' => $e->getMessage()], 403);
        } catch (\Exception $e) {
            return new JsonResponse(['error' => $e->getMessage()], 403);
        }
    }

    #[Route('/stripe/create_checkout_session', name: 'stripe_create_checkout_session', methods: ['POST'])]
    public function stripeCreateCheckoutSession(Request $request): JsonResponse
    {
        try {
            \Stripe\Stripe::setApiKey('sk_FAKE');
            \Stripe\Stripe::$apiBase = 'http://internal_server:8089';

            $data   = json_decode($request->getContent(), true);
            $result = \Stripe\Checkout\Session::create($data);

            return new JsonResponse($result->toArray());
        } catch (\Stripe\Exception\ApiErrorException $e) {
            return new JsonResponse(['error' => $e->getMessage()], 500);
        } catch (\Exception $e) {
            return new JsonResponse(['error' => $e->getMessage()], 500);
        }
    }

    #[Route('/stripe/create_payment_intent', name: 'stripe_create_payment_intent', methods: ['POST'])]
    public function stripeCreatePaymentIntent(Request $request): JsonResponse
    {
        try {
            \Stripe\Stripe::setApiKey('sk_FAKE');
            \Stripe\Stripe::$apiBase = 'http://internal_server:8089';

            $data   = json_decode($request->getContent(), true);
            $result = \Stripe\PaymentIntent::create($data);

            return new JsonResponse($result->toArray());
        } catch (\Stripe\Exception\ApiErrorException $e) {
            return new JsonResponse(['error' => $e->getMessage()], 500);
        } catch (\Exception $e) {
            return new JsonResponse(['error' => $e->getMessage()], 500);
        }
    }
}
