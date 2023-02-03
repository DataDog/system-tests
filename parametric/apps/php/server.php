<?php

ini_set("datadog.trace.generate_root_span", "0");
ini_set("datadog.trace.revolt_enabled", "0");

require __DIR__ . "/vendor/autoload.php";

use Amp\ByteStream;
use Amp\Http\Server\DefaultErrorHandler;
use Amp\Http\Server\Request;
use Amp\Http\Server\RequestHandler\ClosureRequestHandler;
use Amp\Http\Server\Response;
use Amp\Http\Server\Router;
use Amp\Http\Server\SocketHttpServer;
use Amp\Log\ConsoleFormatter;
use Amp\Log\StreamHandler;
use League\Uri\Components\Query;
use Monolog\Logger;
use Monolog\Processor\PsrLogMessageProcessor;
use function Amp\trapSignal;

$logHandler = new StreamHandler(ByteStream\getStdout());
$logHandler->pushProcessor(new PsrLogMessageProcessor);
$logHandler->setFormatter(new ConsoleFormatter);
$logger = new Logger('server');
$logger->pushHandler($logHandler);

$server = new SocketHttpServer($logger);

$server->expose("0.0.0.0:80");

$errorHandler = new DefaultErrorHandler;

function jsonResponse($array) {
    return new Response(headers: ['content-type' => 'application/json'], body: json_encode($array));
}

function arg($req, $arg, bool $array = false) {
    return Query::createFromUri($req->getUri())->{$array ? "getAll" : "get"}($arg);
}

$spans = [];

$router = new Router($server, $errorHandler);
$router->addRoute('GET', '/start_span', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    if ($parent = arg($req, 'parent_id')) {
        \DDTrace\switch_stack($spans[$parent]);
        \DDTrace\create_stack();
        $span = \DDTrace\start_span();
    } else {
        $span = \DDTrace\start_trace_span();
    }
    if ($headers = arg($req, 'http_headers', true)) {
        \DDTrace\consume_distributed_tracing_headers(function ($headername) use ($headers) {
            return $headers[strtolower($headername)] ?? null;
        });
    }
    $span->service = arg($req, 'service');
    $span->type = arg($req, 'type');
    $span->resource = arg($req, 'resource');
    $spans[$span->id] = $span;
    return jsonResponse([
        "span_id" => $span->id,
        "trace_id" => \DDTrace\trace_id(),
    ]);
}));
$router->addRoute('GET', '/inject_headers', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $span = $spans[arg($req, 'span_id')];
    \DDTrace\switch_stack($span);
    return jsonResponse(\DDTrace\generate_distributed_tracing_headers());
}));
$router->addRoute('GET', '/set_tag', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $span = $spans[arg($req, 'span_id')];
    $span->meta[arg($req, 'key')] = arg($req, 'value');
    return jsonResponse([]);
}));
$router->addRoute('GET', '/span_set_error', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $span = $spans[arg($req, 'span_id')];
    $span->meta['error.msg'] = arg($req, 'message');
    $span->meta['error.type'] = arg($req, 'type');
    $span->meta['error.stack'] = arg($req, 'stack');
    return jsonResponse([]);
}));
$router->addRoute('GET', '/finish_span', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $span_id = arg($req, 'span_id');
    \DDTrace\switch_stack($spans[$span_id]);
    \DDTrace\close_span();
    unset($spans[$span_id]);
    return jsonResponse([]);
}));
$router->addRoute('GET', '/flush_spans', new ClosureRequestHandler(function () use (&$spans) {
    \DDTrace\flush();
    return jsonResponse([]);
}));

$server->start($router, $errorHandler);

$signal = trapSignal([SIGINT, SIGTERM]);
$logger->info("Caught signal $signal, stopping server");

$server->stop();
