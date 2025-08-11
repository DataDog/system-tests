# frozen_string_literal: true

require 'net/http'
require 'uri'
require 'json'
require 'faraday'

# tracer configuration of Rack integration

begin
  require 'datadog/auto_instrument'
rescue LoadError
  require 'ddtrace/auto_instrument'
end

require 'datadog/kit/appsec/events'
require 'datadog/kit/appsec/events/v2'

Datadog.configure do |c|
  c.diagnostics.debug = true
  if c.respond_to?(:tracing)
    c.tracing.instrument :rack
  else
    c.use :rack, service_name: ENV['DD_SERVICE'] || 'rack'
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

use Datadog::AppSec::Contrib::Rack::RequestBodyMiddleware if ENV['DD_APPSEC_ENABLED'] == 'true'

# Send non-web init event

if defined?(Datadog::Tracing)
  Datadog::Tracing.trace('init.service') {}
else
  Datadog.tracer.trace('init.service') {}
end

# /
module Hello
  module_function

  def run
    [200, { 'Content-Type' => 'text/plain' }, ['Hello, wat is love?']]
  end
end

# /healthcheck
module Healthcheck
  module_function

  def run
    gemspec = Gem.loaded_specs['datadog'] || Gem.loaded_specs['ddtrace']
    version = gemspec.version.to_s
    version = "#{version}-dev" unless gemspec.source.is_a?(Bundler::Source::Rubygems)
    response = {
      status: 'ok',
      library: {
        name: 'ruby',
        version: version
      }
    }

    [
      200,
      { 'Content-Type' => 'application/json' },
      [response.to_json]
    ]
  end
end

# /spans
module Spans
  module_function

  def run(request)
    repeats = Integer(request.params['repeats'] || 0)
    garbage = Integer(request.params['garbage'] || 0)

    repeats.times do |i|
      Datadog::Tracing.trace("repeat-#{i}") do |span|
        garbage.times do |j|
          span.set_tag("garbage-#{j}", j.to_s)
        end
      end
    end

    [200, { 'Content-Type' => 'text/plain' }, ["Generated #{repeats} spans with #{garbage} garbage tags"]]
  rescue ArgumentError
    [400, { 'Content-Type' => 'text/plain' }, ['bad request']]
  end
end

# /headers
module Headers
  module_function

  def run
    [
      200,
      { 'Content-Type' => 'text/plain', 'Content-Length' => '42', 'Content-Language' => 'en-US' },
      ['Hello, headers!']
    ]
  end
end

# /identify
module Identify
  module_function

  def run
    trace = Datadog::Tracing.active_trace
    trace.set_tag('usr.id', 'usr.id')
    trace.set_tag('usr.name', 'usr.name')
    trace.set_tag('usr.email', 'usr.email')
    trace.set_tag('usr.session_id', 'usr.session_id')
    trace.set_tag('usr.role', 'usr.role')
    trace.set_tag('usr.scope', 'usr.scope')

    [200, { 'Content-Type' => 'text/plain' }, ['Hello, wat is love?']]
  end
end

# /status
module Status
  module_function

  def run(request)
    code = Integer(request.params['code'] || 200)

    [code, { 'Content-Type' => 'text/plain' }, ['Ok']]
  rescue ArgumentError
    [400, { 'Content-Type' => 'text/plain' }, ['bad request']]
  end
end

# /make_distant_call
module MakeDistantCall
  module_function

  def run(request)
    url = request.params['url']
    uri = URI(url)
    request = nil
    response = nil

    Net::HTTP.start(uri.host, uri.port) do |http|
      request = Net::HTTP::Get.new(uri)

      response = http.request(request)
    end

    result = {
      url: url,
      status_code: response.code,
      request_headers: request.each_header.to_h,
      response_headers: response.each_header.to_h
    }

    [200, { 'Content-Type' => 'application/json' }, [result.to_json]]
  end
end

# /user_login_success_event
module UserLoginSuccessEvent
  module_function

  def run
    Datadog::Kit::AppSec::Events.track_login_success(
      Datadog::Tracing.active_trace, user: { id: 'system_tests_user' }, metadata0: 'value0', metadata1: 'value1'
    )

    [200, { 'Content-Type' => 'text/plain' }, ['Ok']]
  end
end

# /user_login_failure_event
module UserLoginFailureEvent
  module_function

  def run
    Datadog::Kit::AppSec::Events.track_login_failure(
      Datadog::Tracing.active_trace,
      user_id: 'system_tests_user',
      user_exists: true,
      metadata0: 'value0',
      metadata1: 'value1'
    )

    [200, { 'Content-Type' => 'text/plain' }, ['Ok']]
  end
end

# /custom_event
module CustomEvent
  module_function

  def run
    Datadog::Kit::AppSec::Events.track('system_tests_event',
                                       Datadog::Tracing.active_trace,
                                       metadata0: 'value0',
                                       metadata1: 'value1')

    [200, { 'Content-Type' => 'text/plain' }, ['Ok']]
  end
end

# /requestdownstream
module RequestDownstream
  module_function

  def run
    uri = URI('http://localhost:7777/returnheaders')
    request = nil
    response = nil

    Net::HTTP.start(uri.host, uri.port) do |http|
      request = Net::HTTP::Get.new(uri)

      response = http.request(request)
    end

    [200, { 'Content-Type' => 'application/json' }, [response.body]]
  end
end

# /returnheaders
module ReturnHeaders
  module_function

  def run(request)
    request_headers = request.each_header.to_h.select do |k, _v|
      k.start_with?('HTTP_') || k == 'CONTENT_TYPE' || k == 'CONTENT_LENGTH'
    end
    request_headers = request_headers.transform_keys do |k|
      k.sub(/^HTTP_/, '').split('_').map(&:capitalize).join('-')
    end

    [200, { 'Content-Type' => 'application/json' }, [request_headers.to_json]]
  end
end

# contains tag_value
module TagValue
  module_function

  def run(request)
    tag_value, status_code = request.path.split('/').select { |p| !p.empty? && p != 'tag_value' }
    trace = Datadog::Tracing.active_trace
    trace.set_tag('appsec.events.system_tests_appsec_event.value', tag_value)

    headers = request.params.each.with_object({}) do |(key, value), hash|
      hash[key] = value
    end

    [status_code, headers, ['Value tagged']]
  end
end

# contains /users
module Users
  module_function

  def run(request)
    user_id = request.params['user']

    Datadog::Kit::Identity.set_user(id: user_id)

    [200, { 'Content-Type' => 'text/plain' }, ['Hello, user!']]
  end
end

# /rasp/ssrf
module SSRFHandler
  module_function

  def run(request)
    url = URI.parse(request.params['domain'])
    url = "http://#{url}" unless url.scheme

    Faraday.get(url)

    [200, { 'Content-Type' => 'text/plain' }, ['']]
  end
end

# TODO: This require shouldn't be needed. `SpanEvent` should be loaded by default.
# TODO: This is likely a bug in the Ruby tracer.
require 'datadog/tracing/span_event'

# /add_event
module AddEvent
  module_function

  def run(_request)
    Datadog::Tracing.active_span.span_events << Datadog::Tracing::SpanEvent.new(
      'span.event', attributes: { string: 'value', int: 1 }
    )

    [200, { 'Content-Type' => 'application/json' }, ['Event added']]
  end
end

# /api_security/sampling/:status
module ApiSecurityWithSampling
  module_function

  def run(request)
    status = request.path.split('/').last
    status_code = status.to_i

    [status_code, { 'Content-Type' => 'application/json' }, ['OK']]
  end
end

# /api_security_sampling/:i
module ApiSecuritySampling
  module_function

  def run(request)
    [200, { 'Content-Type' => 'application/json' }, ['Hello!']]
  end
end

# POST /user_login_success_event_v2
module UserLoginSuccessEventV2
  module_function

  def run(request)
    request.body.rewind
    payload = JSON.parse(request.body.read)

    Datadog::Kit::AppSec::Events::V2.track_user_login_success(
      payload['login'],
      payload['user_id'],
      payload.fetch('metadata', {}).transform_keys(&:to_sym)
    )

    [200, { 'Content-Type' => 'text/plain' }, ['OK']]
  end
end

# POST /user_login_failure_event_v2
module UserLoginFailureEventV2
  module_function

  def run(request)
    request.body.rewind
    payload = JSON.parse(request.body.read)

    Datadog::Kit::AppSec::Events::V2.track_user_login_failure(
      payload['login'],
      payload.fetch('exists', 'false') == 'true',
      payload.fetch('metadata', {}).transform_keys(&:to_sym)
    )

    [200, { 'Content-Type' => 'text/plain' }, ['OK']]
  end
end

# any other route
module NotFound
  module_function

  def run
    [404, { 'Content-Type' => 'text/plain' }, ['not found']]
  end
end

# NOTE: This is a workaround to ensure that the trace was sampled before the
#       request lifecycle ends, like in other higher level frameworks (Rails, Sinatra, etc.).
class TraceSamplingMiddleware
  def initialize(app)
    @app = app
  end

  def call(env)
    response = @app.call(env)
    Datadog.send(:components).tracer.sampler.sample!(Datadog::Tracing.active_trace)
    response
  end
end

use TraceSamplingMiddleware

# /flush
module Flush
  module_function

  def run(request)
    # NOTE: If anything needs to be flushed here before the test suite ends,
    #       this is the place to do it.
    #       See https://github.com/DataDog/system-tests/blob/64539d1d19d14e0ab040d8e4a01562da1531b7d5/docs/internals/flushing.md
    if (telemetry = Datadog.send(:components)&.telemetry)
      telemetry.instance_variable_get(:@worker)&.loop_wait_time = 0

      # HACK: In the current implementation there is no way to force the flushing.
      #       Instead we are giving us a fraction of time after setting `loop_wait_time`
      #       and just wait till all penging messages are flushed.
      #
      # NOTE: Be aware that system-tests doesn't like slow responses, so change that
      #       value carefully.
      sleep 0.2
    end

    [200, { 'Content-Type' => 'text/plain' }, ['OK']]
  end
end

# trivial rack endpoint. We use a proc instead of Rack Builder because
# we compare the request path using regexp and include?
app = proc do |env|
  request = Rack::Request.new(env)

  if request.path == '/' || request.path =~ %r{^/waf(?:/.*|)$} || request.path =~ %r{^/params(?:/.*|)$} || request.path =~ %r{^/sample_rate_route(?:/.*|)$}
    # %r{^/params(?:/.*|)$} doesn't really makes sense for Rack as it does not put the
    # value anywhere for AppSec to receive it
    Hello.run
  elsif request.path == '/healthcheck'
    Healthcheck.run
  elsif request.path == '/spans'
    Spans.run(request)
  elsif request.path == '/headers'
    Headers.run
  elsif request.path == '/identify'
    Identify.run
  elsif request.path.include?('/status')
    Status.run(request)
  elsif request.path == '/make_distant_call'
    MakeDistantCall.run(request)
  elsif request.path == '/user_login_success_event'
    UserLoginSuccessEvent.run
  elsif request.path == '/user_login_failure_event'
    UserLoginFailureEvent.run
  elsif request.path == '/custom_event'
    CustomEvent.run
  elsif request.path == '/requestdownstream'
    RequestDownstream.run
  elsif request.path == '/returnheaders'
    ReturnHeaders.run(request)
  elsif request.path.include?('tag_value')
    TagValue.run(request)
  elsif request.path.include?('/users')
    Users.run(request)
  elsif request.path == '/add_event'
    AddEvent.run(request)
  elsif request.path == '/rasp/ssrf'
    SSRFHandler.run(request)
  elsif request.path.include?('/api_security/sampling/')
    ApiSecurityWithSampling.run(request)
  elsif request.path.include?('/api_security_sampling/')
    ApiSecuritySampling.run(request)
  elsif request.path == '/user_login_success_event_v2'
    UserLoginSuccessEventV2.run(request)
  elsif request.path == '/user_login_failure_event_v2'
    UserLoginFailureEventV2.run(request)
  elsif request.path == '/flush'
    Flush.run(request)
  else
    NotFound.run
  end
end

run app
