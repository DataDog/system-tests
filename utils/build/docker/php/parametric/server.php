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
use Monolog\Logger;
use Monolog\Processor\PsrLogMessageProcessor;
use OpenTelemetry\API\Trace\Propagation\TraceContextPropagator;
use OpenTelemetry\API\Trace\Span;
use OpenTelemetry\API\Trace\SpanKind;
use OpenTelemetry\API\Trace\StatusCode;
use OpenTelemetry\Context\ScopeInterface;
use OpenTelemetry\SDK\Trace as SDK;
use OpenTelemetry\SDK\Trace\TracerProvider;
use function Amp\trapSignal;

$logHandler = new StreamHandler(ByteStream\getStdout());
$logHandler->pushProcessor(new PsrLogMessageProcessor);
$logHandler->setFormatter(new ConsoleFormatter);
$logger = new Logger('server');
$logger->pushHandler($logHandler);

$server = SocketHttpServer::createForDirectAccess($logger);

$port = getenv('APM_TEST_CLIENT_SERVER_PORT');
$server->expose("0.0.0.0:" . $port);

$errorHandler = new DefaultErrorHandler;

function jsonResponse($array) {
    return new Response(headers: ['content-type' => 'application/json'], body: json_encode($array));
}

function arg($req, $arg) {
    static $buffer = new WeakMap;
    return ($buffer[$req] ??= json_decode($req->getBody()->buffer(), true))[$arg] ?? null;
}

function remappedSpanKind($spanKind) {
    switch ($spanKind) {
        case 1: // SK_INTERNAL
            return SpanKind::KIND_INTERNAL;
        case 2: // SK_SERVER
            return SpanKind::KIND_SERVER;
        case 3: // SK_CLIENT
            return SpanKind::KIND_CLIENT;
        case 4: // SK_PRODUCER
            return SpanKind::KIND_PRODUCER;
        case 5: // SK_CONSUMER
            return SpanKind::KIND_CONSUMER;
        default:
            return null;
    }
}

$closed_spans = $spans = [];
/** @var ScopeInterface[] $scopes */
$scopes = [];

$router = new Router($server, $logger, $errorHandler);
$router->addRoute('POST', '/trace/span/start', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    if ($parent = arg($req, 'parent_id')) {
        \DDTrace\switch_stack($spans[$parent]);
        \DDTrace\create_stack();
        $span = \DDTrace\start_span();
    } else {
        $span = \DDTrace\start_trace_span();
    }
    $link_from_headers = null;
    $links = [];
    if ($span_links = arg($req, 'links')) {
        foreach ($span_links as $span_link) {
            if ($parent = $span_link["parent_id"]) {
                $links[] = $link = $spans[$parent]->getLink();
                if (isset($span_link["attributes"])) {
                    $link->attributes += $span_link["attributes"];
                }
            } else {
                $link_from_headers = $span_link;
                $headers_link = &$links[];
            }
        }
    }
    if ($headers = arg($req, 'http_headers')) {
        $headers = array_merge(...array_map(fn($h) => [strtolower($h[0]) => $h[1]], $headers));
        $callback = function ($headername) use ($headers) {
            return $headers[$headername] ?? null;
        };
        if ($link_from_headers) {
            $headers_link = \DDTrace\SpanLink::fromHeaders($callback);
            if (isset($link_from_headers["attributes"])) {
                $headers_link->attributes += $link_from_headers["attributes"];
            }
            var_dump($headers_link->samplingPriority);
            \DDTrace\set_priority_sampling($headers_link->samplingPriority);
            $span->meta += $headers_link->extractedAttributes;
        } else {
            \DDTrace\consume_distributed_tracing_headers($callback);
        }
    }
    if ($origin = arg($req, 'origin')) {
        $context = \DDTrace\current_context();
        \DDTrace\set_distributed_tracing_context($context["trace_id"], $context["distributed_tracing_parent_id"] ?? 0, $origin);
    }
    $span->name = arg($req, 'name');
    $span->service = arg($req, 'service');
    $span->type = arg($req, 'type');
    $span->resource = arg($req, 'resource');
    $span->links = $links;
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
    $span->metrics[arg($req, 'key')] = arg($req, 'value');
    return jsonResponse([]);
}));
$router->addRoute('POST', '/trace/span/error', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $span = $spans[arg($req, 'span_id')];
    $span->meta['error.msg'] = arg($req, 'message');
    $span->meta['error.type'] = arg($req, 'type');
    $span->meta['error.stack'] = arg($req, 'stack');
    return jsonResponse([]);
}));
$router->addRoute('POST', '/trace/span/add_link', new ClosureRequestHandler(function (Request $req) use (&$spans, &$closed_spans) {
    $span = $spans[arg($req, 'span_id')];
    $parent_id = arg($req, 'parent_id');
    $span->links[] = $link = ($spans[$parent_id] ?? $closed_spans[$parent_id])->getLink();
    $link->attributes += arg($req, "attributes") ?? [];
    return jsonResponse([]);
}));
$router->addRoute('POST', '/trace/span/finish', new ClosureRequestHandler(function (Request $req) use (&$spans, &$closed_spans) {
    $span_id = arg($req, 'span_id');
    \DDTrace\switch_stack($spans[$span_id]);
    \DDTrace\close_span();
    $closed_spans[$span_id] = $spans[$span_id];
    unset($spans[$span_id]);
    return jsonResponse([]);
}));
$router->addRoute('POST', '/trace/span/flush', new ClosureRequestHandler(function () use (&$spans) {
    \DDTrace\flush();
    dd_trace_internal_fn("synchronous_flush");
    return jsonResponse([]);
}));
$router->addRoute('POST', '/trace/otel/start_span', new ClosureRequestHandler(function (Request $req) use (&$spans, &$scopes) {
    $name = arg($req, 'name');
    $timestamp = arg($req, 'timestamp');
    $spanKind = arg($req, 'span_kind');
    $parentId = arg($req, 'parent_id');
    $httpHeaders = arg($req, 'http_headers');
    $attributes = arg($req, 'attributes');

    $tracer = (new TracerProvider())->getTracer('OpenTelemetry.PHPTestTracer');

    $spanBuilder = $tracer->spanBuilder($name);
    if ($parentId) {
        /** @var ?Span $parentSpan */
        $parentSpan = $spans[$parentId];
        if ($parentSpan === null) {
            return jsonResponse([]);
        }
        $contextWithParentSpan = $parentSpan->storeInContext(OpenTelemetry\Context\Context::getRoot());
        $spanBuilder->setParent($contextWithParentSpan);
    }

    $spanKind = remappedSpanKind($spanKind);
    if ($spanKind !==  null) {
        $spanBuilder->setSpanKind($spanKind);
    }

    if ($timestamp) {
        $spanBuilder->setStartTimestamp($timestamp * 1000); // ms -> ns
    }

    if ($httpHeaders) {
        $carrier = [];
        foreach ($httpHeaders as $headers) {
            $carrier[$headers[0]] = $headers[1];
        }
        $remoteContext = TraceContextPropagator::getInstance()->extract($carrier);
        $spanBuilder->setParent($remoteContext);
    }

    if ($attributes) {
        $spanBuilder->setAttributes($attributes);
    }

    $span = $spanBuilder->startSpan();
    $spanId = $span->getContext()->getSpanId();
    $traceId = $span->getContext()->getTraceId();
    $scopes[$spanId] = $span->activate();
    $spans[$spanId] = $span;

    return jsonResponse([
        'span_id' => $spanId,
        'trace_id' => $traceId
    ]);
}));
$router->addRoute('POST', '/trace/otel/end_span', new ClosureRequestHandler(function (Request $req) use (&$spans, &$scopes) {
    $spanId = arg($req, 'id');
    $timestamp = arg($req, 'timestamp');

    /** @var ?Span $span */
    $span = $spans[$spanId];
    if ($span) {
        $scope = $scopes[$spanId];
        $scope?->detach();
        $span->end($timestamp ? $timestamp * 1000 : null);
    }

    return jsonResponse([]);
}));
$router->addRoute('POST', '/trace/otel/set_attributes', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $spanId = arg($req, 'span_id');
    $attributes = arg($req, 'attributes');

    /** @var ?Span $span */
    $span = $spans[$spanId];
    if ($span) {
        $span->setAttributes($attributes);
    }

    return jsonResponse([]);
}));
$router->addRoute('POST', '/trace/otel/set_name', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $spanId = arg($req, 'span_id');
    $name = arg($req, 'name');

    /** @var ?Span $span */
    $span = $spans[$spanId];
    if ($span) {
        $span->updateName($name);
    }

    return jsonResponse([]);
}));
$router->addRoute('POST', '/trace/otel/set_status', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $spanId = arg($req, 'span_id');
    $code = arg($req, 'code');
    $description = arg($req, 'description');

    switch ($code) {
        case 'UNSET':
            $code = StatusCode::STATUS_UNSET;
            break;
        case 'OK':
            $code = StatusCode::STATUS_OK;
            break;
        case 'ERROR':
            $code = StatusCode::STATUS_ERROR;
            break;
    }

    /** @var ?Span $span */
    $span = $spans[$spanId];
    $span?->setStatus($code, $description);

    return jsonResponse([]);
}));
$router->addRoute('POST', '/trace/otel/flush', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    \DDTrace\flush();
    dd_trace_internal_fn("synchronous_flush");
     return jsonResponse([
         'success' => true
     ]);
}));
$router->addRoute('POST', '/trace/otel/is_recording', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $spanId = arg($req, 'span_id');

    /** @var ?Span $span */
    $span = $spans[$spanId];
    if ($span) {
        return jsonResponse([
            'is_recording' => $span->isRecording()
        ]);
    }

    return jsonResponse([]);
}));
$router->addRoute('POST', '/trace/otel/span_context', new ClosureRequestHandler(function (Request $req) use (&$spans) {
    $spanId = arg($req, 'span_id');

    /** @var ?SDK\Span $span */
    $span = $spans[$spanId];
    if ($span) {
        $spanContext = $span->getContext();

        return jsonResponse([
            'trace_id' => $spanContext->getTraceId(),
            'span_id' => $spanContext->getSpanId(),
            'trace_flags' => $spanContext->getTraceFlags() ? '01' : '00',
            'trace_state' => (string) $spanContext->getTraceState(), // Implements __toString()
            'remote' => $spanContext->isRemote()
        ]);
    }

    return jsonResponse([]);
}));
$server->start($router, $errorHandler);

$signal = trapSignal([SIGINT, SIGTERM]);
$logger->info("Caught signal $signal, stopping server");

$server->stop();
