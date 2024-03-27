require 'pry'
require "net/http"
require "uri"
require 'json'

# tracer configuration of Rack integration

require 'datadog/auto_instrument'
require 'datadog/kit/appsec/events'

Datadog.configure do |c|
  c.diagnostics.debug = true
  if c.respond_to?(:tracing)
    c.tracing.instrument :rack
  else
    c.use :rack, service_name: (ENV['DD_SERVICE'] || 'rack')
  end
end

if defined?(Datadog::Tracing)
  use Datadog::Tracing::Contrib::Rack::TraceMiddleware
else
  use Datadog::Contrib::Rack::TraceMiddleware
end

if ENV['DD_APPSEC_ENABLED'] == 'true'
  Datadog.configure do |c|
    c.appsec.enabled = true
    c.appsec.instrument :rack
  end

  use Datadog::AppSec::Contrib::Rack::RequestMiddleware
end

require 'rack/contrib/json_body_parser'
use Rack::JSONBodyParser

if ENV['DD_APPSEC_ENABLED'] == 'true'
  use Datadog::AppSec::Contrib::Rack::RequestBodyMiddleware
end


# Send non-web init event

if defined?(Datadog::Tracing)
  Datadog::Tracing.trace('init.service') { }
else
  Datadog.tracer.trace('init.service') { }
end

# trivial rack endpoint

app = proc do |env|
  request = Rack::Request.new(env)

  if request.path == '/'
    [ 200, {'Content-Type' => 'text/plain'}, ['Hello, wat is love?'] ]
  elsif request.path =~ /^\/waf(?:\/.*|)$/
    [ 200, {'Content-Type' => 'text/plain'}, ['Hello, wat is love?'] ]
  elsif request.path =~ /^\/params(?:\/.*|)$/
    # this route doesn't really makes sense for Rack as it does not put the
    # value anywhere for AppSec to receive it
    [ 200, {'Content-Type' => 'text/plain'}, ['Hello, wat is love?'] ]
  elsif request.path == '/spans'
    begin
      repeats = Integer(request.params['repeats'] || 0)
      garbage = Integer(request.params['garbage'] || 0)
    rescue ArgumentError
      [ 400, {'Content-Type' => 'text/plain'}, ['bad request'] ]
    else
      repeats.times do |i|
        Datadog::Tracing.trace('repeat-#{i}') do |span|
          garbage.times do |j|
            span.set_tag("garbage-#{j}", "#{j}")
          end
        end
      end

      [ 200, {'Content-Type' => 'text/plain'}, ['Generated #{repeats} spans with #{garbage} garbage tags'] ]
    end
  elsif request.path == '/headers'
    [ 200, {'Content-Type' => 'text/plain', 'Content-Length' => '42', 'Content-Language' => 'en-US'}, ['Hello, headers!'] ]
  elsif request.path == '/identify'
    trace = Datadog::Tracing.active_trace
    trace.set_tag('usr.id', 'usr.id')
    trace.set_tag('usr.name', 'usr.name')
    trace.set_tag('usr.email', 'usr.email')
    trace.set_tag('usr.session_id', 'usr.session_id')
    trace.set_tag('usr.role', 'usr.role')
    trace.set_tag('usr.scope', 'usr.scope')

    [ 200, {'Content-Type' => 'text/plain'}, ['Hello, wat is love?'] ]
  elsif request.path.include?('/status')
    [ request.params["code"].to_i, {'Content-Type' => 'text/plain'}, ['Ok'] ]
  elsif request.path == '/make_distant_call'
    url = request.params["url"]
    uri = URI(url)
    request = nil
    response = nil

    Net::HTTP.start(uri.host, uri.port) do |http|
      request = Net::HTTP::Get.new(uri)

      response = http.request(request)
    end

    result = {
      "url": url,
      "status_code": response.code,
      "request_headers": request.each_header.to_h,
      "response_headers": response.each_header.to_h,
    }

    [200, { 'Content-Type' => 'application/json' }, [ result.to_json ]]
  elsif request.path == '/user_login_success_event'
    Datadog::Kit::AppSec::Events.track_login_success(
      Datadog::Tracing.active_trace, user: {id: 'system_tests_user'}, metadata0: "value0", metadata1: "value1"
    )

    [ 200, {'Content-Type' => 'text/plain'}, ['Ok'] ]
  elsif  request.path == '/user_login_failure_event'
    Datadog::Kit::AppSec::Events.track_login_failure(
      Datadog::Tracing.active_trace, user_id: 'system_tests_user', user_exists: true, metadata0: "value0", metadata1: "value1"
    )

    [ 200, {'Content-Type' => 'text/plain'}, ['Ok'] ]
  elsif request.path ==  '/custom_event'
    Datadog::Kit::AppSec::Events.track('system_tests_event', Datadog::Tracing.active_trace,  metadata0: "value0", metadata1: "value1")

    [ 200, {'Content-Type' => 'text/plain'}, ['Ok'] ]
  elsif request.path.include?('tag_value')
		tag_value, status_code = request.path.split('/').select { |p| !p.empty? && p != 'tag_value' }
    trace = Datadog::Tracing.active_trace
    trace.set_tag("appsec.events.system_tests_appsec_event.value", tag_value)

    headers = request.params.each.with_object({}) do |(key, value), hash|
      hash[key] = value
    end

    [ status_code, headers, ['Value tagged'] ]
  elsif request.path.include?('/users')
    user_id = request.params["user"]

    Datadog::Kit::Identity.set_user(id: user_id)

    [ 200, {'Content-Type' => 'text/plain'}, ['Hello, user!'] ]
  else
    [ 404, {'Content-Type' => 'text/plain'}, ['not found'] ]
  end
end

run app
