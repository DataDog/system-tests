require 'opentelemetry/sdk'
require 'datadog/opentelemetry'

Datadog.configure do |c|
  c.diagnostics.debug = true
end

::OpenTelemetry::SDK.configure do |_c|
end

# Send non-web init event

if defined?(Datadog::Tracing)
  Datadog::Tracing.trace('init.service') { }
else
  Datadog.tracer.trace('init.service') { }
end
