#!/usr/bin/env bash
# Install everything the five conformance backends need. Idempotent: safe to
# re-run. Prerequisites NOT installed here (fail with a message if missing):
#   temper, node + npm, python3, dotnet SDK, maven, and a JDK 17+.
# Auto-installed: JS npm deps, a Python venv (.venv-ddtrace), a Go 1.25
# toolchain, the .NET NuGet packages, and the dd-java-agent jar.
set -euo pipefail
cd "$(dirname "$0")"

GO_VER=1.25.11
GO_ROOT="$HOME/toolchains/go1.25/go"
DD_JAVA_VER=1.63.2

need() { command -v "$1" >/dev/null 2>&1 || { echo "MISSING prerequisite: $1 — install it first ($2)"; exit 1; }; }

# Resolve a JDK 17+ java (the generated Java suite is Java 17 bytecode).
find_java17() {
  for c in /opt/homebrew/opt/openjdk@17/bin/java /opt/homebrew/opt/openjdk/bin/java; do
    [ -x "$c" ] && { echo "$c"; return 0; }
  done
  if [ -x /usr/libexec/java_home ]; then
    local h; h=$(/usr/libexec/java_home -v 17+ 2>/dev/null || true); [ -n "$h" ] && { echo "$h/bin/java"; return 0; }
  fi
  command -v java || true
}

echo "== checking prerequisites =="
need temper "https://temperlang.dev/"
need node   "https://nodejs.org/"
need python3 "https://python.org/"
need dotnet "https://dotnet.microsoft.com/download"
need mvn    "https://maven.apache.org/ (brew install maven)"
need cargo  "https://rustup.rs/ (for the dd-trace-ruby/php rust cdylib)"
need php    "https://www.php.net/ (brew install php) — 8.x with FFI, for dd-trace-php"
need composer "https://getcomposer.org/ (brew install composer) — for the dd-trace-php OTel deps"
find_ruby() { for c in /opt/homebrew/opt/ruby/bin/ruby /opt/homebrew/opt/ruby@3.4/bin/ruby /opt/homebrew/opt/ruby@3.3/bin/ruby; do [ -x "$c" ] && { echo "$c"; return 0; }; done; command -v ruby || true; }
RUBY=$(find_ruby)
[ -n "$RUBY" ] && "$RUBY" --version >/dev/null 2>&1 || { echo "MISSING prerequisite: Ruby 3.x (brew install ruby)"; exit 1; }
JAVA17=$(find_java17)
[ -n "$JAVA17" ] && "$JAVA17" -version >/dev/null 2>&1 || { echo "MISSING prerequisite: a JDK 17+ (brew install openjdk@17)"; exit 1; }
echo "  temper, node $(node -v), python3, dotnet $(dotnet --version), mvn $(mvn -v 2>/dev/null | head -1 | awk '{print $3}'), java17 -> $JAVA17"

echo "== [1/8] dd-trace-js: npm deps =="
npm --prefix adapters/dd-trace-js install --silent
node -e "console.log('  dd-trace', require('./adapters/dd-trace-js/node_modules/dd-trace/package.json').version)"

echo "== [2/8] dd-trace-py: venv + ddtrace + test-agent =="
[ -d .venv-ddtrace ] || python3 -m venv .venv-ddtrace
./.venv-ddtrace/bin/pip install --quiet --upgrade pip
./.venv-ddtrace/bin/pip install --quiet ddtrace opentelemetry-api msgpack ddapm-test-agent
./.venv-ddtrace/bin/python -c "import ddtrace; print('  ddtrace', ddtrace.__version__)"

echo "== [3/8] dd-trace-go: Go ${GO_VER} toolchain (v2 requires Go 1.25) =="
if [ ! -x "$GO_ROOT/bin/go" ]; then
  os=$(uname -s | tr '[:upper:]' '[:lower:]'); arch=$(uname -m)
  case "$arch" in x86_64|amd64) arch=amd64;; arm64|aarch64) arch=arm64;; *) echo "unsupported arch $arch"; exit 1;; esac
  mkdir -p "$(dirname "$GO_ROOT")"
  curl -fsSL "https://go.dev/dl/go${GO_VER}.${os}-${arch}.tar.gz" | tar -xz -C "$(dirname "$GO_ROOT")"
fi
"$GO_ROOT/bin/go" version | sed 's/^/  /'

echo "== [4/8] dd-trace-dotnet: NuGet restore (Datadog.Trace + Datadog.Trace.Bundle) =="
temper build -b csharp >/dev/null
dotnet restore adapters/dd-trace-dotnet >/dev/null
echo "  restored"

echo "== [5/8] dd-trace-java: generated artifacts + dd-java-agent =="
temper build -b java >/dev/null
python3 adapters/dd-trace-java/patch_tracer.py   # work around a temper java default-arg codegen bug
for p in temper-core std system-tests-redux; do
  mvn -q -f "temper.out/java/$p/pom.xml" install -DskipTests -Dgpg.skip=true
done
[ -f adapters/dd-trace-java/dd-java-agent.jar ] || \
  curl -fsSL -o adapters/dd-trace-java/dd-java-agent.jar \
    "https://repo1.maven.org/maven2/com/datadoghq/dd-java-agent/${DD_JAVA_VER}/dd-java-agent-${DD_JAVA_VER}.jar"
mvn -q -f adapters/dd-trace-java/pom.xml package
echo "  dd-java-agent ${DD_JAVA_VER} + conformance.jar ready"

echo "== [6/8] dd-trace-ruby: datadog gem + rust cdylib =="
"$RUBY" -S gem list -i datadog >/dev/null 2>&1 || "$RUBY" -S gem install --no-document datadog
bash adapters/dd-trace-ruby/build.sh >/dev/null    # temper build -b rust + patch_mod.py + cargo build cdylib
echo "  datadog gem + libstr_ruby_shim cdylib ready"

echo "== [7/8] dd-trace-php: ddtrace extension (FFI drives the shared cdylib) =="
find_php() { for c in /opt/homebrew/opt/php/bin/php /opt/homebrew/opt/php@8.4/bin/php /opt/homebrew/opt/php@8.3/bin/php; do [ -x "$c" ] && { echo "$c"; return 0; }; done; command -v php || true; }
PHP=$(find_php)
[ -n "$PHP" ] || { echo "MISSING prerequisite: PHP 8.x with FFI (brew install php)"; exit 1; }
if ! "$PHP" -m 2>/dev/null | grep -qi '^ddtrace'; then
  # dd-trace-php needs the pcre2 header on the include path on macOS/arm64.
  PCRE2=$(brew --prefix pcre2 2>/dev/null)/include
  printf "\n" | CFLAGS="-I$PCRE2" CPPFLAGS="-I$PCRE2" "$(dirname "$PHP")/pecl" install datadog_trace
fi
"$PHP" -m 2>/dev/null | grep -qi '^ddtrace' && echo "  ddtrace $("$PHP" -r 'echo phpversion("ddtrace");') + FFI ready"
( cd adapters/dd-trace-php && composer install --no-interaction )   # open-telemetry/api+sdk for the otel_* cases
echo "  open-telemetry sdk (composer) ready"

echo "== [8/8] dd-trace-rust: native crate + dd-trace-rs (cargo git dep) =="
( cd adapters/dd-trace-rust && cargo build --release )   # fetches dd-trace-rs from git + links the generated suite crate
echo "  dd-trace-rust binary ready"

echo "== setup complete — now run ./run-all.sh =="
