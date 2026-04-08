Datadog.configure do |c|
  c.diagnostics.debug = true
  c.appsec.instrument :active_record
  c.tracing.log_injection = true if ENV['CONFIG_CHAINING_TEST'] == 'true'
end

# Send non-web init event

if defined?(Datadog::Tracing)
  Datadog::Tracing.trace('init.service') { }
else
  Datadog.tracer.trace('init.service') { }
end
