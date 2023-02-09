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

function arg($req, $arg) {
    static $buffer = new WeakMap;
    return ($buffer[$req] ??= json_decode($req->getBody()->buffer(), true))[$arg] ?? null;
}

$spans = [];

$router = new Router($server, $errorHandler);
$router->addRoute('POST', '/trace/span/start', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    if ($parent = arg($req, 'parent_id')) {
        \DDTrace\switch_stack($spans[$parent]);
        \DDTrace\create_stack();
        $span = \DDTrace\start_span();
    } else {
        $span = \DDTrace\start_trace_span();
    }
    if ($headers = arg($req, 'http_headers')) {
        $headers = array_merge(...array_map(fn($h) => [$h[0] => $h[1]], $headers));
        \DDTrace\consume_distributed_tracing_headers(function ($headername) use ($headers) {
            return $headers[strtolower($headername)] ?? null;
        });
    }
    if ($origin = arg($req, 'origin')) {
        $context = \DDTrace\current_context();
        \DDTrace\set_distributed_tracing_context($context["trace_id"], $context["distributed_tracing_parent_id"] ?? 0, $origin);
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
$router->addRoute('POST', '/trace/span/inject_headers', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $span = $spans[arg($req, 'span_id')];
    \DDTrace\switch_stack($span);
    $headers = \DDTrace\generate_distributed_tracing_headers();
    return jsonResponse(["http_headers" => array_map(null, array_keys($headers), $headers)]);
}));
$router->addRoute('POST', '/trace/span/set_meta', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $span = $spans[arg($req, 'span_id')];
    $span->meta[arg($req, 'key')] = arg($req, 'value');
    return jsonResponse([]);
}));
$router->addRoute('POST', '/trace/span/set_metric', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $span = $spans[arg($req, 'span_id')];
    $span->metric[arg($req, 'key')] = arg($req, 'value');
    return jsonResponse([]);
}));
$router->addRoute('POST', '/trace/span/error', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $span = $spans[arg($req, 'span_id')];
    $span->meta['error.msg'] = arg($req, 'message');
    $span->meta['error.type'] = arg($req, 'type');
    $span->meta['error.stack'] = arg($req, 'stack');
    return jsonResponse([]);
}));
$router->addRoute('POST', '/trace/span/finish', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $span_id = arg($req, 'span_id');
    \DDTrace\switch_stack($spans[$span_id]);
    \DDTrace\close_span();
    unset($spans[$span_id]);
    return jsonResponse([]);
}));
$router->addRoute('POST', '/trace/span/flush', new ClosureRequestHandler(function () use (&$spans) {
    \DDTrace\flush();
    return jsonResponse([]);
}));

$server->start($router, $errorHandler);

$signal = trapSignal([SIGINT, SIGTERM]);
$logger->info("Caught signal $signal, stopping server");

$server->stop();
