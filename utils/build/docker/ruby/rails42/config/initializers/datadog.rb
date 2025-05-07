Datadog.configure do |c|
  c.diagnostics.debug = true
  c.appsec.instrument :active_record
end

# Send non-web init event

if defined?(Datadog::Tracing)
  Datadog::Tracing.trace('init.service') {}
else
  Datadog.tracer.trace('init.service') {}
end
