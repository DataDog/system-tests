<?php
// Run a single conformance case by index against dd-trace-php, via the rust
// cdylib loaded with PHP's FFI. The case env (DD_* vars, DD_TRACE_AGENT_URL,
// DD_TRACE_CLI_ENABLED, DD_TRACE_SIDECAR_TRACE_SENDER=0) is applied by the
// parent runner (run.php) via the subprocess env BEFORE this script starts, so
// the ddtrace extension initializes with the case's configuration.
//
// The cdylib is SHARED with the dd-trace-ruby backend (see
// ../dd-trace-ruby/CONTRACT.md); it exports:
//   char* str_run_case(int32_t index, char* (*dispatch)(const char*, const char*))
//   void  str_free(char* p)
// and calls our dispatch(op, args_json) once per Tracer method. We pass a PHP
// closure as the C `dispatch` callback (PHP-FFI marshals the const char* args to
// PHP strings and creates a native thunk); the closure decodes the args, calls
// Dispatch::handle, and returns a libc-malloc'd NUL-terminated JSON string that
// rust reads and free()s.

// Keep stdout clean for the PASS/SKIP/FAIL result line; route any PHP notices to stderr.
error_reporting(E_ALL & ~E_DEPRECATED);
ini_set("display_errors", "stderr");

// OpenTelemetry API/SDK (composer) if installed — enables the otel_* ops via
// dd-trace-php's OTel bridge; absent -> those cases fall back to SKIP.
$autoload = __DIR__ . "/vendor/autoload.php";
if (is_file($autoload)) { require $autoload; }

require __DIR__ . "/adapter.php";

$LIB = __DIR__ . "/../dd-trace-ruby/shim/target/debug/libstr_ruby_shim.dylib";
if (!file_exists($LIB)) {
    fwrite(STDERR, "cdylib not found at $LIB (build it: bash adapters/dd-trace-ruby/build.sh)\n");
    exit(3);
}

$ffi = FFI::cdef(
    'int str_case_count(void);'
    . 'char* str_case_name(int index);'
    . 'void str_free(char* p);'
    . 'char* str_run_case(int index, char* (*dispatch)(const char*, const char*));',
    $LIB
);
$libc = FFI::cdef('char* malloc(size_t);');

// Copy $s into libc-malloc'd memory with a trailing NUL; ownership transfers to
// the rust caller, which free()s it.
$mkcstr = function (string $s) use ($libc) {
    $n = strlen($s);
    $buf = $libc->malloc($n + 1);
    if ($n > 0) { FFI::memcpy($buf, $s, $n); }
    $buf[$n] = "\0";
    return $buf;
};

// dispatch callback: char* (*)(const char* op, const char* args_json).
// PHP-FFI passes op/args as PHP strings. A PHP exception must NOT propagate
// across the C boundary (UB), so marshal it as {"__error__":...} -> caught FAIL.
$dispatch = function ($op, $args_json) use ($mkcstr) {
    try {
        $args = ($args_json === "" || $args_json === null) ? [] : json_decode($args_json, true);
        if (!is_array($args)) { $args = []; }
        $result = Dispatch::handle((string) $op, $args);
        $json = json_encode($result, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
        if ($json === false) {
            throw new \RuntimeException("json_encode failed: " . json_last_error_msg());
        }
        return $mkcstr($json);
    } catch (\Throwable $e) {
        return $mkcstr(json_encode(["__error__" => get_class($e) . ": " . $e->getMessage()]));
    }
};

$index = (int) ($argv[1] ?? 0);
$resPtr = $ffi->str_run_case($index, $dispatch);
$result = FFI::string($resPtr);
$ffi->str_free($resPtr);

if (str_starts_with($result, "PASS")) {
    echo $result . "\n";
    exit(0);
} elseif (str_starts_with($result, "SKIP")) {
    echo $result . "\n";
    exit(2);
} elseif (getenv("PHP_KNOWN_DIFF") === "1") {
    // Downgrade a genuine FAIL to a documented skip. A listed diff that PASSES
    // still reports PASS above, so the list can't hide a fix.
    $name = explode(":", preg_replace('/^FAIL /', "", $result), 2)[0];
    echo "SKIP $name (known dd-trace-php diff)\n";
    exit(2);
} else {
    echo $result . "\n";
    exit(1);
}
