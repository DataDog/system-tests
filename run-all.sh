#!/usr/bin/env bash
# Build + run all four conformance backends against their real dd-trace library,
# printing the one-line summary for each. Run ./setup.sh once first.
# Pass a backend name (js|py|go|dotnet) to run just one.
set -uo pipefail
cd "$(dirname "$0")"

GO_ROOT="$HOME/toolchains/go1.25/go"
only="${1:-all}"
rc=0

find_java17() {
  for c in /opt/homebrew/opt/openjdk@17/bin/java /opt/homebrew/opt/openjdk/bin/java; do
    [ -x "$c" ] && { echo "$c"; return 0; }
  done
  if [ -x /usr/libexec/java_home ]; then
    local h; h=$(/usr/libexec/java_home -v 17+ 2>/dev/null || true); [ -n "$h" ] && { echo "$h/bin/java"; return 0; }
  fi
  command -v java || true
}

run_js() {
  echo "== dd-trace-js (npm dd-trace) =="
  temper build -b js >/dev/null
  node adapters/dd-trace-js/run.mjs 2>/dev/null | tail -1 || rc=1
}
run_py() {
  echo "== dd-trace-py (pip ddtrace) =="
  temper build -b py >/dev/null
  ./.venv-ddtrace/bin/python adapters/dd-trace-py/run.py 2>/dev/null | tail -1 || rc=1
}
run_go() {
  echo "== dd-trace-go (dd-trace-go/v2, native C-FFI) =="
  temper build -b py >/dev/null          # the go driver runs on the Python backend
  ( cd adapters/dd-trace-go && GOROOT="$GO_ROOT" GOTOOLCHAIN=local CGO_ENABLED=1 \
      "$GO_ROOT/bin/go" build -buildmode=c-shared -o libddtracego.dylib . ) 2>/dev/null
  ./.venv-ddtrace/bin/python adapters/dd-trace-go/run.py 2>/dev/null | tail -1 || rc=1
}
run_dotnet() {
  echo "== dd-trace-dotnet (Datadog.Trace v3 under the CLR profiler) =="
  temper build -b csharp >/dev/null
  dotnet build adapters/dd-trace-dotnet -v q >/dev/null || { echo "  build failed"; rc=1; return; }
  dotnet adapters/dd-trace-dotnet/bin/Debug/net6.0/conformance.dll 2>/dev/null | tail -1 || rc=1
}
run_java() {
  echo "== dd-trace-java (dd-trace-java under -javaagent, OTel API) =="
  local j17; j17=$(find_java17)
  temper build -b java >/dev/null
  python3 adapters/dd-trace-java/patch_tracer.py   # work around a temper java default-arg codegen bug
  for p in temper-core std system-tests-redux; do
    mvn -q -f "temper.out/java/$p/pom.xml" install -DskipTests -Dgpg.skip=true >/dev/null 2>&1
  done
  mvn -q -f adapters/dd-trace-java/pom.xml package >/dev/null 2>&1 || { echo "  build failed"; rc=1; return; }
  "$j17" -cp adapters/dd-trace-java/target/conformance.jar ddtracejava.Main 2>/dev/null | tail -1 || rc=1
}
find_ruby() {
  for c in /opt/homebrew/opt/ruby/bin/ruby /opt/homebrew/opt/ruby@3.4/bin/ruby /opt/homebrew/opt/ruby@3.3/bin/ruby; do
    [ -x "$c" ] && { echo "$c"; return 0; }
  done
  command -v ruby || true
}
run_ruby() {
  echo "== dd-trace-ruby (dd-trace-rb via rust cdylib + Fiddle) =="
  local rb; rb=$(find_ruby)
  bash adapters/dd-trace-ruby/build.sh >/dev/null 2>&1 || { echo "  cdylib build failed"; rc=1; return; }
  "$rb" adapters/dd-trace-ruby/run.rb 2>/dev/null | tail -1 || rc=1
}
find_php() {
  for c in /opt/homebrew/opt/php/bin/php /opt/homebrew/opt/php@8.4/bin/php /opt/homebrew/opt/php@8.3/bin/php; do
    [ -x "$c" ] && { echo "$c"; return 0; }
  done
  command -v php || true
}
run_php() {
  echo "== dd-trace-php (dd-trace-php via rust cdylib + FFI) =="
  local php; php=$(find_php)
  bash adapters/dd-trace-ruby/build.sh >/dev/null 2>&1 || { echo "  cdylib build failed"; rc=1; return; }
  [ -f adapters/dd-trace-php/vendor/autoload.php ] || \
    ( cd adapters/dd-trace-php && composer install --no-interaction >/dev/null 2>&1 )  # OTel deps for otel_* cases
  "$php" adapters/dd-trace-php/run.php 2>/dev/null | tail -1 || rc=1
}
run_rust() {
  echo "== dd-trace-rust (native Temper crate -> dd-trace-rs, no FFI) =="
  ( cd adapters/dd-trace-rust && cargo build --release >/dev/null 2>&1 ) || { echo "  cargo build failed"; rc=1; return; }
  .venv-ddtrace/bin/python adapters/dd-trace-rust/run.py 2>/dev/null | tail -1 || rc=1
}

pkill -f ddapm-test-agent 2>/dev/null || true; sleep 1
case "$only" in
  js) run_js;; py) run_py;; go) run_go;; dotnet) run_dotnet;; java) run_java;; ruby) run_ruby;; php) run_php;; rust) run_rust;;
  all) run_js; run_py; run_go; run_dotnet; run_java; run_ruby; run_php; run_rust;;
  *) echo "usage: $0 [js|py|go|dotnet|java|ruby|php|rust]"; exit 2;;
esac
exit $rc
