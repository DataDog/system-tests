<?php
// dd-trace-php implementation of the Temper-generated Tracer interface.
//
// Mirrors the dd-trace-ruby adapter: implements the conformance `Tracer` surface
// against the real `ddtrace` Zend extension, using the SAME primitives the
// upstream system-tests PHP parametric client uses
// (utils/build/docker/php/parametric/server.php):
//
//   - roots     : \DDTrace\start_trace_span()
//   - children  : \DDTrace\switch_stack($parent); \DDTrace\create_stack(); \DDTrace\start_span()
//   - extracted : \DDTrace\start_span() + \DDTrace\consume_distributed_tracing_headers($cb)
//   - finish    : \DDTrace\switch_stack($span); \DDTrace\close_span()
//   - inject    : \DDTrace\switch_stack($span); \DDTrace\generate_distributed_tracing_headers()
//
// Spans are read back from the ddapm-test-agent (captured_spans/delivered_spans),
// so the capture reflects the real on-the-wire serialization. Span/trace ids are
// decimal strings (trace id is the low 64 bits, matching the agent payload).
//
// The rust cdylib (see ../dd-trace-ruby/CONTRACT.md) calls Dispatch::handle($op,
// $args) once per Tracer method; `$op` is the snake_case method name and `$args`
// is the decoded JSON args array. `handle` returns a plain PHP value that
// run_one.php encodes to the CONTRACT JSON. Unimplemented ops return
// ["__unsupported__" => true] so the case SKIPs (matching the other adapters).

final class Dispatch
{
    /** @var array<string, object> decimal span id -> SpanData (open) */
    private static array $spans = [];
    /** @var array<string, object> decimal span id -> SpanData (finished) */
    private static array $closed = [];
    /** @var array<string, array<string,string>> parent id -> extracted headers map */
    private static array $distHeaders = [];
    /** @var array<string, array{trace_hex:string,span_hex:string}> parent id -> link ids */
    private static array $distCtx = [];
    private static int $ctxCounter = 0;
    /** @var array<string, object> decimal span id -> OTel span (bridged to DD) */
    private static array $otelSpans = [];
    /** @var array<string, object> decimal span id -> OTel context scope */
    private static array $otelScopes = [];

    public static function handle(string $op, array $args)
    {
        try {
            switch ($op) {
                case "start_span":      return self::startSpan(...$args);
                case "finish_span":     return self::finishSpan(...$args);
                case "set_meta":        return self::setMeta(...$args);
                case "set_metric":      return self::setMetric(...$args);
                case "set_resource":    return self::setResource(...$args);
                case "remove_meta":     return self::removeMeta(...$args);
                case "remove_metric":   return self::removeMetric(...$args);
                case "add_link":        return self::addLink(...$args);
                case "extract_headers": return self::extractHeaders($args[0] ?? []);
                case "inject_headers":  return self::injectHeaders(...$args);
                case "flush":           return self::flush();
                case "captured_spans":  return self::capturedSpans();
                case "delivered_spans": return self::capturedSpans();
                case "config":          return self::config();
                case "otel_start_span":       return self::otelStartSpan(...$args);
                case "otel_end_span":         return self::otelEndSpan(...$args);
                case "otel_set_attribute":     return self::otelSetAttribute(...$args);
                case "otel_set_attribute_num": return self::otelSetAttributeNum(...$args);
                case "otel_is_recording":     return self::otelIsRecording(...$args);
                case "otel_span_context":     return self::otelSpanContext(...$args);
                case "otel_set_status":       return self::otelSetStatus(...$args);
                case "otel_record_exception": return self::otelRecordException(...$args);
                case "otel_add_event":        return self::otelAddEvent(...$args);
                case "otel_remove_attribute":
                    // The OpenTelemetry span API has no attribute removal (go/java
                    // skip this too) -> genuine gap.
                    return ["__unsupported__" => true];
                default:
                    // baggage (no manual API in dd-trace-php), otel_* (needs the
                    // opentelemetry-sdk composer package + bridge), telemetry/RC/
                    // stats (not driveable from the manual API) -> SKIP.
                    return ["__unsupported__" => true];
            }
        } catch (\Throwable $e) {
            // An op that blows up is treated as unsupported so the case SKIPs
            // rather than aborting; run_one.php surfaces the reason.
            return ["__unsupported__" => true, "error" => get_class($e) . ": " . $e->getMessage()];
        }
    }

    // --- span lifecycle ------------------------------------------------------

    private static function startSpan($name, $parentId, $service = "", $resource = "", $spanType = "")
    {
        $hasParent = !self::blank($parentId) && $parentId !== "0";

        if ($hasParent && isset(self::$spans[$parentId])) {
            // child of a known local span: re-root at the parent, then isolate
            // the child on its own stack so siblings can be added later.
            \DDTrace\switch_stack(self::$spans[$parentId]);
            \DDTrace\create_stack();
            $span = \DDTrace\start_span();
        } elseif ($hasParent && isset(self::$distHeaders[$parentId])) {
            // child of an extracted remote context: a fresh trace re-parented to
            // the remote span by re-consuming the stored carrier (yields a single
            // delivered span attached to the remote parent).
            $hdrs = self::$distHeaders[$parentId];
            $span = \DDTrace\start_trace_span();
            \DDTrace\consume_distributed_tracing_headers(
                fn($h) => $hdrs[strtolower($h)] ?? null
            );
        } else {
            // root of a new trace.
            $span = \DDTrace\start_trace_span();
        }

        $span->name = $name;
        if (!self::blank($service))  { $span->service = $service; }
        if (!self::blank($resource)) { $span->resource = $resource; }
        if (!self::blank($spanType)) { $span->type = $spanType; }

        $sid = (string) $span->id;
        self::$spans[$sid] = $span;

        return self::stub($span, $hasParent ? (string) $parentId : "0", $name, $service, $resource, $spanType);
    }

    private static function finishSpan($spanId)
    {
        $span = self::$spans[$spanId] ?? null;
        if ($span) {
            \DDTrace\switch_stack($span);
            \DDTrace\close_span();
            self::$closed[$spanId] = $span;
            unset(self::$spans[$spanId]);
        }
        return null;
    }

    private static function setMeta($spanId, $key, $value)
    {
        $s = self::span($spanId);
        if ($s) { $s->meta[$key] = (string) $value; }
        return null;
    }

    private static function setMetric($spanId, $key, $value)
    {
        $s = self::span($spanId);
        if ($s) { $s->metrics[$key] = 0.0 + $value; }
        return null;
    }

    private static function setResource($spanId, $value)
    {
        $s = self::span($spanId);
        if ($s) { $s->resource = $value; }
        return null;
    }

    private static function removeMeta($spanId, $key)
    {
        $s = self::span($spanId);
        if ($s) { unset($s->meta[$key]); }
        return null;
    }

    private static function removeMetric($spanId, $key)
    {
        $s = self::span($spanId);
        if ($s) { unset($s->metrics[$key]); }
        return null;
    }

    private static function addLink($spanId, $linkToSpanId, $attributes)
    {
        $span = self::span($spanId);
        if (!$span) { return null; }
        $target = self::span($linkToSpanId);
        if (!$target) {
            // link target is an extracted remote context, not a local span.
            if (isset(self::$distCtx[$linkToSpanId])) {
                self::addLinkToContext($span, $linkToSpanId, $attributes);
            }
            return null;
        }

        $attrs = self::strVals($attributes ?? []);
        $link = $target->getLink();
        $link->attributes = ($link->attributes ?? []) + $attrs;
        $span->links[] = $link;
        return null;
    }

    private static function addLinkToContext($span, string $linkToSpanId, $attributes): void
    {
        $ctx = self::$distCtx[$linkToSpanId];
        $link = new \DDTrace\SpanLink();
        $link->traceId = $ctx["trace_hex"];
        $link->spanId = $ctx["span_hex"];
        $attrs = self::strVals($attributes ?? []);
        if (!empty($attrs)) { $link->attributes = $attrs; }
        $span->links[] = $link;
    }

    // --- distributed headers -------------------------------------------------

    private static function extractHeaders($headers)
    {
        $map = [];
        foreach (($headers ?? []) as $pair) {
            // HTTP headers are case-insensitive; dd-trace-php reads lowercase.
            $k = strtolower((string) $pair[0]);
            // Fold repeated headers (RFC 7230) so duplicate traceparent/tracestate/
            // baggage inputs are represented faithfully in the single-value carrier.
            $map[$k] = isset($map[$k]) ? $map[$k] . "," . $pair[1] : (string) $pair[1];
        }
        // Consume WITHOUT creating a span (a throwaway span would otherwise get
        // delivered and break findOnlySpan); read the extracted parent id from the
        // distributed context. The child span is (re)built from the stored carrier
        // in startSpan's extracted-parent branch.
        \DDTrace\consume_distributed_tracing_headers(
            fn($h) => $map[strtolower($h)] ?? null
        );
        $ctx = \DDTrace\current_context();
        $pid = $ctx["distributed_tracing_parent_id"] ?? null;
        // Reset the ambient distributed context (incl. origin + propagated tags)
        // so it doesn't leak into a later unrelated root/linking span in the case.
        \DDTrace\set_distributed_tracing_context("0", "0", "", []);

        if ($pid !== null && $pid !== "" && $pid !== 0 && $pid !== "0") {
            $pid = (string) $pid;
            self::$distHeaders[$pid] = $map;
            // Remember the extracted ids (as 128-bit hex) so a span link *to* this
            // remote context can be built without a local span.
            $tags = $ctx["distributed_tracing_propagated_tags"] ?? [];
            self::$distCtx[$pid] = [
                "trace_hex" => self::traceHex((string) ($ctx["trace_id"] ?? "0"), (string) ($tags["_dd.p.tid"] ?? "")),
                "span_hex"  => self::decToHex16($pid),
            ];
            return $pid;
        }
        // A trace-less context that still carries baggage: keep the carrier so a
        // child started from it inherits the baggage (baggage-only propagation).
        $bagKey = "bgctx" . (++self::$ctxCounter);
        if (isset($map["baggage"])) {
            self::$distHeaders[$bagKey] = $map;
            return $bagKey;
        }
        return "0";
    }

    private static function injectHeaders($spanId)
    {
        $span = self::span($spanId);
        if (!$span) { return new \stdClass(); }
        \DDTrace\switch_stack($span);
        $headers = \DDTrace\generate_distributed_tracing_headers();
        $out = [];
        foreach ($headers as $k => $v) { $out[(string) $k] = (string) $v; }
        return empty($out) ? new \stdClass() : $out;
    }

    // --- flush + capture -----------------------------------------------------

    private static function flush()
    {
        // Synchronous flush to the agent (legacy sender; the sidecar sender is
        // disabled by the runner env). A conformance case calls flush before
        // reading spans back, and the per-case process exits right after.
        \dd_trace_synchronous_flush(2000);
        return null;
    }

    private static function capturedSpans()
    {
        self::flush();
        $all = self::spansFromAgent();
        // Keep only spans the adapter created. The OpenTelemetry SDK's resource
        // detectors run shell/curl calls that ddtrace auto-instruments into stray
        // spans (command_execution, curl_exec); those aren't part of the case and
        // would break findOnlySpan. DD-API cases deliver exactly their own span,
        // so this filter is a no-op for them.
        $created = array_flip(array_map(
            'strval',
            array_merge(array_keys(self::$spans), array_keys(self::$closed))
        ));
        $mine = array_filter($all, fn($s) => isset($created[(string) ($s["span_id"] ?? "")]));
        return array_values($mine);
    }

    // --- resolved config -----------------------------------------------------

    private static function config()
    {
        $e = fn($k) => \dd_trace_env_config($k);
        return [
            "dd_service"                 => self::sOrNull($e("DD_SERVICE")),
            "dd_env"                     => self::sOrNull($e("DD_ENV")),
            "dd_version"                 => self::sOrNull($e("DD_VERSION")),
            "dd_trace_agent_url"         => self::sOrNull($e("DD_TRACE_AGENT_URL")),
            "dd_trace_sample_rate"       => self::sOrNull($e("DD_TRACE_SAMPLE_RATE")),
            "dd_trace_rate_limit"        => self::sOrNull($e("DD_TRACE_RATE_LIMIT")),
            "dd_trace_enabled"           => self::boolLow($e("DD_TRACE_ENABLED")),
            "dd_trace_debug"             => self::boolLow($e("DD_TRACE_DEBUG")),
            "dd_runtime_metrics_enabled" => "false", // PHP has no DD_RUNTIME_METRICS_ENABLED
            "dd_trace_otel_enabled"      => self::boolLow($e("DD_TRACE_OTEL_ENABLED")),
            "dd_trace_propagation_style" => self::propStyle($e("DD_TRACE_PROPAGATION_STYLE")),
            "dd_tags"                    => self::tagsCsv($e("DD_TAGS")),
            "dd_log_level"               => self::sOrNull($e("DD_TRACE_LOG_LEVEL")),
        ];
    }

    // --- helpers -------------------------------------------------------------

    // --- OpenTelemetry API (bridged to DD spans by ddtrace when DD_TRACE_OTEL_
    // ENABLED=true; the OTel span becomes a normal DD span on the wire, so
    // captured_spans reads it back from the agent unchanged) -----------------

    private static function otelTracer()
    {
        static $tracer = null;
        if ($tracer === null) {
            $tracer = (new \OpenTelemetry\SDK\Trace\TracerProvider())->getTracer("conformance");
        }
        return $tracer;
    }

    private static function otelKind($kind)
    {
        switch (strtolower((string) $kind)) {
            case "server":   return \OpenTelemetry\API\Trace\SpanKind::KIND_SERVER;
            case "client":   return \OpenTelemetry\API\Trace\SpanKind::KIND_CLIENT;
            case "producer": return \OpenTelemetry\API\Trace\SpanKind::KIND_PRODUCER;
            case "consumer": return \OpenTelemetry\API\Trace\SpanKind::KIND_CONSUMER;
            default:         return \OpenTelemetry\API\Trace\SpanKind::KIND_INTERNAL;
        }
    }

    private static function otelStartSpan($name, $parentId, $kind = "internal")
    {
        $sb = self::otelTracer()->spanBuilder((string) $name);
        $hasParent = !self::blank($parentId) && $parentId !== "0";
        $parentSpan = null;
        if ($hasParent) {
            if (isset(self::$otelSpans[$parentId])) {
                $parentSpan = self::$otelSpans[$parentId];
            } elseif (isset(self::$spans[$parentId])) {
                // DD-API parent: reconcile the active stack, adopt its OTel view.
                \DDTrace\switch_stack(self::$spans[$parentId]);
                $parentSpan = \OpenTelemetry\API\Trace\Span::getCurrent();
                self::$otelSpans[$parentId] = $parentSpan;
            }
        }
        if ($parentSpan !== null) {
            $sb->setParent($parentSpan->storeInContext(\OpenTelemetry\Context\Context::getRoot()));
        } else {
            // explicit root: don't inherit any ambient context.
            $sb->setParent(\OpenTelemetry\Context\Context::getRoot());
        }
        $sb->setSpanKind(self::otelKind($kind));

        $span = $sb->startSpan();
        $scope = $span->activate();
        $dd = $span->getDDSpan();
        $sid = (string) $dd->id;
        self::$otelSpans[$sid] = $span;
        self::$otelScopes[$sid] = $scope;
        self::$spans[$sid] = $dd;
        return self::stub($dd, $hasParent ? (string) $parentId : "0", $dd->name, $dd->service ?? "", $dd->resource ?? "", "");
    }

    private static function otelEndSpan($spanId)
    {
        $span = self::$otelSpans[$spanId] ?? null;
        if ($span) {
            $scope = self::$otelScopes[$spanId] ?? null;
            if ($scope) { $scope->detach(); }
            $span->end();
            $dd = $span->getDDSpan();
            if ($dd) { self::$closed[$spanId] = $dd; }
            unset(self::$spans[$spanId], self::$otelScopes[$spanId]);
        }
        return null;
    }

    private static function otelSetAttribute($spanId, $key, $value)
    {
        $span = self::$otelSpans[$spanId] ?? null;
        if ($span) { $span->setAttribute((string) $key, (string) $value); }
        return null;
    }

    private static function otelSetAttributeNum($spanId, $key, $value)
    {
        $span = self::$otelSpans[$spanId] ?? null;
        if ($span) {
            $num = 0.0 + $value;
            // integral -> int, else float (OTel numeric attribute).
            $span->setAttribute((string) $key, ($num == (int) $num) ? (int) $num : $num);
        }
        return null;
    }

    private static function otelIsRecording($spanId)
    {
        $span = self::$otelSpans[$spanId] ?? null;
        return $span ? (bool) $span->isRecording() : false;
    }

    private static function otelSpanContext($spanId)
    {
        $span = self::$otelSpans[$spanId] ?? null;
        if (!$span) { return ["trace_id_hex" => "", "span_id_hex" => ""]; }
        $ctx = $span->getContext();
        return ["trace_id_hex" => $ctx->getTraceId(), "span_id_hex" => $ctx->getSpanId()];
    }

    private static function otelSetStatus($spanId, $code, $description = "")
    {
        $span = self::$otelSpans[$spanId] ?? null;
        if ($span) {
            switch (strtoupper((string) $code)) {
                case "OK":    $c = \OpenTelemetry\API\Trace\StatusCode::STATUS_OK; break;
                case "ERROR": $c = \OpenTelemetry\API\Trace\StatusCode::STATUS_ERROR; break;
                default:      $c = \OpenTelemetry\API\Trace\StatusCode::STATUS_UNSET; break;
            }
            $span->setStatus($c, (string) $description);
        }
        return null;
    }

    private static function otelRecordException($spanId, $message, $attributes = [])
    {
        $span = self::$otelSpans[$spanId] ?? null;
        if ($span) {
            $attrs = is_array($attributes) ? $attributes : [];
            $span->recordException(new \Exception((string) $message), $attrs);
        }
        return null;
    }

    private static function otelAddEvent($spanId, $name, $timeMicros = 0, $attrs = [])
    {
        $span = self::$otelSpans[$spanId] ?? null;
        if ($span) {
            $assoc = [];
            foreach ((array) $attrs as $a) {
                if (!isset($a["key"])) { continue; }
                $assoc[$a["key"]] = self::otelEventValue($a["kind"] ?? "string", $a["values"] ?? []);
            }
            $span->addEvent((string) $name, $assoc, ((int) $timeMicros) * 1000);
        }
        return null;
    }

    private static function otelEventValue($kind, array $values)
    {
        $k = strtolower((string) $kind);
        $cast = function ($v) use ($k) {
            if (str_contains($k, "bool")) { return filter_var($v, FILTER_VALIDATE_BOOLEAN); }
            if (str_contains($k, "int"))  { return (int) $v; }
            if (str_contains($k, "double") || str_contains($k, "float")) { return (float) $v; }
            return (string) $v;
        };
        $mapped = array_map($cast, (array) $values);
        return count($mapped) === 1 ? $mapped[0] : $mapped;
    }

    private static function span($id)
    {
        return self::$spans[$id] ?? self::$closed[$id] ?? null;
    }

    private static function blank($s): bool
    {
        return $s === null || $s === "";
    }

    /** Low 64 bits of the current trace id, as a decimal string (agent format). */
    private static function traceLow64(): string
    {
        $full = \DDTrace\trace_id(); // 128-bit decimal string
        if ($full === "" || $full === null) { return "0"; }
        return \gmp_strval(\gmp_mod(\gmp_init($full, 10), \gmp_init("18446744073709551616")), 10);
    }

    private static function stub($span, string $parentId, $name, $service, $resource, $spanType): array
    {
        return [
            "trace_id"  => self::traceLow64(),
            "span_id"   => (string) $span->id,
            "parent_id" => $parentId,
            "name"      => (string) $name,
            "service"   => (string) $service,
            "resource"  => (string) $resource,
            "span_type" => (string) $spanType,
            "meta"      => new \stdClass(),
            "metrics"   => new \stdClass(),
            "links"     => [],
            "error"     => null,
        ];
    }

    private static function agentBase(): string
    {
        return rtrim((string) ($_SERVER["DD_TRACE_AGENT_URL"] ?? getenv("DD_TRACE_AGENT_URL") ?: ""), "/");
    }

    private static function agentGet(string $path): ?string
    {
        $base = self::agentBase();
        if ($base === "") { return null; }
        $ch = \curl_init($base . $path);
        \curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 4,
            CURLOPT_CONNECTTIMEOUT => 3,
        ]);
        $body = \curl_exec($ch);
        $code = \curl_getinfo($ch, CURLINFO_HTTP_CODE);
        return ($body !== false && $code >= 200 && $code < 300) ? $body : null;
    }

    private static function spansFromAgent(): array
    {
        $deadline = microtime(true) + 8.0;
        while (microtime(true) < $deadline) {
            $raw = self::agentGet("/test/session/traces");
            // Trace/span ids exceed PHP_INT_MAX; keep them as strings (else they
            // decode to floats like 1.39E+19 and corrupt id matching).
            $traces = $raw ? (json_decode($raw, true, 512, JSON_BIGINT_AS_STRING) ?: []) : [];
            if (!empty($traces)) {
                $out = [];
                foreach ($traces as $trace) {
                    foreach ($trace as $sp) { $out[] = self::agentSpanToCaptured($sp); }
                }
                return $out;
            }
            usleep(300000);
        }
        return [];
    }

    private static function agentSpanToCaptured(array $sp): array
    {
        $meta = [];
        foreach (($sp["meta"] ?? []) as $k => $v) { $meta[(string) $k] = (string) $v; }
        $metrics = [];
        foreach (($sp["metrics"] ?? []) as $k => $v) {
            if (is_numeric($v)) { $metrics[(string) $k] = 0.0 + $v; }
        }
        $links = [];
        $topLinks = $sp["span_links"] ?? [];
        if (empty($topLinks) && isset($sp["meta"]["_dd.span_links"])) {
            // dd-trace-php delivers links in the v0.4 meta tag (128-bit hex ids).
            $decoded = json_decode((string) $sp["meta"]["_dd.span_links"], true);
            foreach ((is_array($decoded) ? $decoded : []) as $l) {
                $tHex = (string) ($l["trace_id"] ?? "");
                $lo = strlen($tHex) > 16 ? substr($tHex, -16) : $tHex;
                $hi = strlen($tHex) > 16 ? substr($tHex, 0, strlen($tHex) - 16) : "";
                $attrs = [];
                foreach (($l["attributes"] ?? []) as $k => $v) { $attrs[(string) $k] = (string) $v; }
                $links[] = [
                    "span_id"       => self::hexToDec((string) ($l["span_id"] ?? "")),
                    "trace_id"      => self::hexToDec($lo),
                    "trace_id_high" => ($hi === "") ? "0" : self::hexToDec($hi),
                    "attributes"    => empty($attrs) ? new \stdClass() : $attrs,
                ];
            }
        }
        foreach ($topLinks as $l) {
            $attrs = [];
            foreach (($l["attributes"] ?? []) as $k => $v) { $attrs[(string) $k] = (string) $v; }
            $links[] = [
                "span_id"       => (string) ($l["span_id"] ?? 0),
                "trace_id"      => (string) ($l["trace_id"] ?? 0),
                "trace_id_high" => (string) ($l["trace_id_high"] ?? 0),
                "attributes"    => empty($attrs) ? new \stdClass() : $attrs,
            ];
        }
        return [
            "trace_id"  => (string) ($sp["trace_id"] ?? 0),
            "span_id"   => (string) ($sp["span_id"] ?? 0),
            "parent_id" => (string) ($sp["parent_id"] ?? 0),
            "name"      => (string) ($sp["name"] ?? ""),
            "service"   => (string) ($sp["service"] ?? ""),
            "resource"  => (string) ($sp["resource"] ?? ""),
            "span_type" => (string) ($sp["type"] ?? ""),
            "meta"      => empty($meta) ? new \stdClass() : $meta,
            "metrics"   => empty($metrics) ? new \stdClass() : $metrics,
            "links"     => $links,
            "error"     => (int) ($sp["error"] ?? 0),
        ];
    }

    /** decimal (possibly 128-bit) trace id + optional _dd.p.tid hex -> 32-char hex */
    private static function traceHex(string $traceDec, string $tidHex): string
    {
        $full = \gmp_init($traceDec === "" ? "0" : $traceDec, 10);
        $mask64 = \gmp_init("18446744073709551616"); // 2^64
        // If the id fits in 64 bits and a high-order _dd.p.tid is present, combine.
        if ($tidHex !== "" && \gmp_cmp($full, $mask64) < 0) {
            $full = \gmp_add(\gmp_mul(\gmp_init($tidHex, 16), $mask64), $full);
        }
        return str_pad(\gmp_strval($full, 16), 32, "0", STR_PAD_LEFT);
    }

    private static function decToHex16(string $dec): string
    {
        return str_pad(\gmp_strval(\gmp_init($dec === "" ? "0" : $dec, 10), 16), 16, "0", STR_PAD_LEFT);
    }

    private static function hexToDec(string $hex): string
    {
        $hex = ltrim($hex, "0");
        return $hex === "" ? "0" : \gmp_strval(\gmp_init($hex, 16), 10);
    }

    private static function strVals(array $a): array
    {
        $out = [];
        foreach ($a as $k => $v) { $out[(string) $k] = (string) $v; }
        return $out;
    }

    private static function sOrNull($v): string
    {
        if ($v === null) { return "null"; }
        if (is_bool($v)) { return $v ? "true" : "false"; }
        if (is_float($v)) {
            // "1.0" -> "1", but keep fractional precision (e.g. 0.1).
            $s = rtrim(rtrim(sprintf("%.10f", $v), "0"), ".");
            return $s === "" ? "0" : $s;
        }
        return (string) $v;
    }

    private static function boolLow($v): string
    {
        if (is_bool($v)) { return $v ? "true" : "false"; }
        if ($v === null || $v === "") { return "false"; }
        return in_array(strtolower((string) $v), ["1", "true", "on", "yes"], true) ? "true" : "false";
    }

    private static function propStyle($v): string
    {
        // dd-trace-php reports its internal style names; map back to the canonical
        // system-tests tokens the suite asserts (inverse of run.php's translation).
        static $back = [
            "b3 single header" => "b3", "b3multi" => "b3multi",
            "datadog" => "datadog", "tracecontext" => "tracecontext",
            "baggage" => "baggage", "none" => "none",
        ];
        $names = is_array($v) ? array_keys($v) : (self::blank($v) ? [] : explode(",", (string) $v));
        if (empty($names)) { return "null"; }
        return implode(",", array_map(fn($n) => $back[strtolower(trim($n))] ?? trim($n), $names));
    }

    private static function tagsCsv($v): string
    {
        if (is_array($v)) {
            if (empty($v)) { return "null"; }
            $out = [];
            foreach ($v as $k => $val) { $out[] = "$k:$val"; }
            return implode(",", $out);
        }
        return self::blank($v) ? "null" : (string) $v;
    }
}
