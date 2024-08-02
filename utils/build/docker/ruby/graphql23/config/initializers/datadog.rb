Datadog.configure do |c|
  c.diagnostics.debug = true

  c.tracing.instrument :graphql, with_unified_tracer: true

  c.appsec.instrument :graphql
end

# Send non-web init event

if defined?(Datadog::Tracing)
  Datadog::Tracing.trace('init.service') { }
else
  Datadog.tracer.trace('init.service') { }
end
