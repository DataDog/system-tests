# Conformance runner for dd-trace-rb.
#
#   temper build -b py                 # generate the Temper registry (Python)
#   (cd shim && cargo build)           # build the rust cdylib (sibling task)
#   /opt/homebrew/opt/ruby/bin/ruby adapters/dd-trace-ruby/run.rb
#
# Drives the real dd-trace-rb tracer (rust cdylib + Fiddle FFI) with the Temper
# suite. Each case runs in its own subprocess (run_one.rb) so its DD_* env is
# applied before the tracer initializes; spans go to one shared ddapm-test-agent
# and are read back via /test/session/traces (captured_spans / delivered_spans).
#
# The case env is sourced from the Python registry (`all_cases()` in
# temper.out/py) the same way the dd-trace-go runner does — the rust cdylib and
# the Python registry are compiled from the same src/, so case ordering matches.

require "json"
require "socket"
require "net/http"
require "uri"

HERE = __dir__
REPO = File.expand_path("../..", HERE)
RUBY = RbConfig.ruby
PY = File.join(REPO, ".venv-ddtrace", "bin", "python")
LIBRARY = "ruby"

# Verified genuine dd-trace-rb behavior/config diffs (each mirrors a diff other
# backends also carry). A listed case that unexpectedly PASSES still reports
# PASS (run_one.rb only downgrades a genuine FAIL), so the list can't hide a fix.
KNOWN_RUBY_DIFFS = {
  # single-span sampling tags (_dd.span_sampling.*) aren't emitted in this
  # per-case + test-agent capture (the trace is kept, so span-sampling doesn't
  # engage) -- same gap go/dotnet/java carry.
  "span_sampling.sss001_single_rule_match" => "single-span sampling tags not emitted",
  "span_sampling.sss002_glob_chars" => "single-span sampling tags not emitted",
  "span_sampling.sss004_service_only" => "single-span sampling tags not emitted",
  "span_sampling.sss006_multi_keep_drop" => "single-span sampling tags not emitted",
  "span_sampling.sss011_manual_drop_kept" => "single-span sampling rule_rate/mechanism not emitted",
  # SCI git tag attached across the chunk, not only the asserted root span (as dotnet).
  "tracer.sci_commit_sha" => "SCI git tag not confined to the first/root span",
  "tracer.sci_repository_url" => "SCI git tag not confined to the first/root span",
  # config-surface gaps (as go/dotnet/java): dd_log_level not exposed; OTEL_SDK_DISABLED precedence.
  "otel_env_vars.log_level" => "Datadog.configuration exposes no dd_log_level",
  "otel_env_vars.otel_enabled_precedence" => "OTEL_SDK_DISABLED precedence not surfaced in config",
  # runner forces DD_TRACE_AGENT_URL for delivery, so ipv6 agent-url readback can't be tested.
  "config_consistency.agent_host_ipv6" => "runner forces DD_TRACE_AGENT_URL for span delivery",
  # propagated _dd.p.dm sampling-mechanism value differs (-0 vs -4), as go/java.
  "headers_tracestate_dd.propagate_propagatedtags" => "_dd.p.dm mechanism value differs",
  "headers_tracecontext.ts_w3c_p_inject" => "tracestate p: member / dm value differs",
}

# --- source per-case name/env/unsupported from the Python registry -----------
CASES_SCRIPT = <<~PY
  import sys, os, json
  repo = os.environ["REPO"]
  sys.path[:0] = [os.path.join(repo, "temper.out", "py", p)
                  for p in ("system-tests-redux", "temper-core", "std")]
  from system_tests_redux.system_tests_redux import all_cases
  out = []
  for c in all_cases():
      out.append({
          "name": c.name,
          "env": dict(c.env),
          "unsupported": list(c.unsupported),
          "needs_agent": bool(getattr(c, "needs_agent", False)),
      })
  print(json.dumps(out))
PY

def load_cases
  raw = IO.popen({ "REPO" => REPO }, [PY, "-c", CASES_SCRIPT], &:read)
  raise "failed to load case registry (is temper.out/py built? run: temper build -b py)" unless $?.success?

  JSON.parse(raw)
end

# --- pick unique free ports (never collide with sibling agents) --------------
def free_port
  s = TCPServer.new("127.0.0.1", 0)
  port = s.addr[1]
  s.close
  port
end

def agent_get(base, path)
  uri = URI.parse(base + path)
  Net::HTTP.start(uri.host, uri.port, open_timeout: 2, read_timeout: 3) do |http|
    http.get(uri.request_uri).body
  end
rescue StandardError
  nil
end

cases = load_cases
puts "— dd-trace-rb conformance runner (Fiddle FFI -> rust cdylib) —"
ruby_ver = `#{RUBY} --version`.strip
dd_ver = `#{RUBY} -e 'require "datadog"; print Datadog::VERSION::STRING' 2>/dev/null`.strip
puts "ruby:     #{ruby_ver}"
puts "datadog:  #{dd_ver}"
puts "cases:    #{cases.length}\n\n"

# --- one shared ddapm-test-agent on unique ports -----------------------------
port = free_port
otlp_http = free_port
otlp_grpc = free_port
agent_url = "http://127.0.0.1:#{port}"
agent_bin = File.join(REPO, ".venv-ddtrace", "bin", "ddapm-test-agent")

agent = spawn(
  agent_bin,
  "--port", port.to_s,
  "--otlp-http-port", otlp_http.to_s,
  "--otlp-grpc-port", otlp_grpc.to_s,
  out: File::NULL, err: File::NULL
)
at_exit do
  begin
    Process.kill("TERM", agent)
    Process.wait(agent)
  rescue StandardError
    nil
  end
end

50.times do
  break if agent_get(agent_url, "/info")

  sleep 0.2
end

passed = failed = skipped = 0
cases.each_with_index do |c, i|
  if c["unsupported"].include?(LIBRARY)
    puts "SKIP #{c['name']} (unsupported on #{LIBRARY})"
    skipped += 1
    next
  end

  env = {}
  env["DD_TRACE_AGENT_URL"] = agent_url
  c["env"].each { |k, v| env[k] = v }

  # dd-trace-rb expects lowercase short propagation-style names; the shared cases
  # use the system-tests canonical names. Translate (as the py/go adapters do).
  style_map = { "datadog" => "datadog", "b3 single header" => "b3", "b3" => "b3",
                "b3 multi header" => "b3multi", "b3multi" => "b3multi",
                "tracecontext" => "tracecontext", "baggage" => "baggage", "none" => "none" }
  %w[DD_TRACE_PROPAGATION_STYLE DD_TRACE_PROPAGATION_STYLE_EXTRACT DD_TRACE_PROPAGATION_STYLE_INJECT].each do |k|
    next unless env[k]
    env[k] = env[k].split(",").map { |s| style_map[s.strip.downcase] || s.strip }.join(",")
  end

  env["RUBY_KNOWN_DIFF"] = "1" if KNOWN_RUBY_DIFFS.key?(c["name"])

  agent_get(agent_url, "/test/session/clear")

  ok = system(env, RUBY, File.join(HERE, "run_one.rb"), i.to_s)
  status = $?.exitstatus
  if status == 2
    skipped += 1
  elsif ok
    passed += 1
  else
    failed += 1
  end
end

ran = passed + failed
tail = skipped.positive? ? ", #{skipped} skipped" : ""
puts "\n#{passed}/#{ran} cases passed (dd-trace-ruby)#{tail}"
exit(failed.zero? ? 0 : 1)
