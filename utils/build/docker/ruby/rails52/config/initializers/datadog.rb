# require 'ddtrace'

Datadog.configure do |c|
  c.diagnostics.debug = true
end

Datadog::Tracing.configure do |c|
  options = {}
  c.instrument :rails, options
end

Datadog::Tracing.trace('init.service') do |span|
end
