# require 'ddtrace'

Datadog.configure do |c|
  c.diagnostics.debug = true
end

Datadog.configure do |c|
  options = {}
  c.use :rails, options
end

Datadog.tracer.trace('init.service') do |span|
end
