require 'opentelemetry/sdk'
require 'datadog/opentelemetry'

Datadog.configure do |c|
  c.diagnostics.debug = true
  c.appsec.instrument :active_record

  # Trace logging should be enabled with general tracer debugging,
  # but it seems the tracer debugging is not enabled via the environment
  # variable.
  #if %w(1 yes true).include?(ENV['DD_TRACE_DEBUG'])
    c.dynamic_instrumentation.internal.trace_logging = true
  #end
end

::OpenTelemetry::SDK.configure do |c|
end

# Send non-web init event

if defined?(Datadog::Tracing)
  Datadog::Tracing.trace('init.service') { }
else
  Datadog.tracer.trace('init.service') { }
end
