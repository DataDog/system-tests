# require 'ddtrace'

Datadog.configure do |c|
  c.diagnostics.debug = true
end

Datadog.configure do |c|
  options = { service_name: ENV['DD_SERVICE'] || 'rails' }
  c.use :rails, options
end

Datadog.tracer.trace('init.service') do |span|
end
