require 'sinatra'
require 'net/http'
require 'uri'
require 'json'
require 'faraday'
require 'sinatra/json'

begin
  require 'datadog/auto_instrument'
rescue LoadError
  require 'ddtrace/auto_instrument'
end

Datadog.configure do |c|
  c.diagnostics.debug = true

  c.use :sinatra, service_name: ENV.fetch('DD_SERVICE', 'sinatra') unless c.respond_to?(:tracing)
end

require 'rack/contrib/json_body_parser'
use Rack::JSONBodyParser

set :strict_paths, false

# Send non-web init event

if defined?(Datadog::Tracing)
  Datadog::Tracing.trace('init.service') {}
else
  Datadog.tracer.trace('init.service') {}
end

get '/' do
  'Hello, world!'
end

get '/healthcheck' do
  content_type :json

  gemspec = Gem.loaded_specs['datadog'] || Gem.loaded_specs['ddtrace']
  version = gemspec.version.to_s
  version = "#{version}-dev" unless gemspec.source.is_a?(Bundler::Source::Rubygems)
  {
    status: 'ok',
    library: {
      name: 'ruby',
      version: version
    }
  }.to_json
end

post '/' do
  'Hello, world!'
end

get '/waf' do
  'Hello, world!'
end

post '/waf' do
  'Hello, world!'
end

get '/waf/:value' do
  'Hello, world!'
end

post '/waf/:value' do
  'Hello, world!'
end

get '/params/:value' do
  'Hello, world!'
end

get '/spans' do
  begin
    repeats = Integer(request.params['repeats'] || 0)
    garbage = Integer(request.params['garbage'] || 0)
  rescue ArgumentError
    response.status = 400

    'bad request'
  else
    repeats.times do |_i|
      Datadog::Tracing.trace('repeat-#{i}') do |span|
        garbage.times do |j|
          span.set_tag("garbage-#{j}", "#{j}")
        end
      end
    end
  end

  'Generated #{repeats} spans with #{garbage} garbage tags'
end

get '/headers' do
  response.headers['Cache-Control'] = 'public, max-age=300'

  response.headers['Content-Type'] = 'text/plain'
  response.headers['Content-Length'] = '15'
  response.headers['Content-Language'] = 'en-US'

  'Hello, headers!'
end

get '/identify' do
  trace = Datadog::Tracing.active_trace
  trace.set_tag('usr.id', 'usr.id')
  trace.set_tag('usr.name', 'usr.name')
  trace.set_tag('usr.email', 'usr.email')
  trace.set_tag('usr.session_id', 'usr.session_id')
  trace.set_tag('usr.role', 'usr.role')
  trace.set_tag('usr.scope', 'usr.scope')

  'Hello, world!'
end

get '/status' do
  code = params['code'].to_i
  status code

  'Ok'
end

get '/make_distant_call' do
  content_type :json

  url = request.params['url']
  uri = URI(url)
  request = nil
  response = nil

  Net::HTTP.start(uri.host, uri.port) do |http|
    request = Net::HTTP::Get.new(uri)

    response = http.request(request)
  end

  result = {
    "url": url,
    "status_code": response.code.to_i,
    "request_headers": request.each_header.to_h,
    "response_headers": response.each_header.to_h
  }

  result.to_json
end

require 'datadog/kit/appsec/events'

get '/user_login_success_event' do
  Datadog::Kit::AppSec::Events.track_login_success(
    Datadog::Tracing.active_trace, user: { id: 'system_tests_user' }, metadata0: 'value0', metadata1: 'value1'
  )

  'Ok'
end

get '/user_login_failure_event' do
  Datadog::Kit::AppSec::Events.track_login_failure(
    Datadog::Tracing.active_trace, user_id: 'system_tests_user', user_exists: true, metadata0: 'value0', metadata1: 'value1'
  )

  'Ok'
end

get '/custom_event' do
  Datadog::Kit::AppSec::Events.track('system_tests_event', Datadog::Tracing.active_trace, metadata0: 'value0',
                                                                                          metadata1: 'value1')

  'Ok'
end

post '/user_login_success_event_v2' do
  require 'datadog/kit/appsec/events/v2'
  request.body.rewind
  params = JSON.parse(request.body.read)

  Datadog::Kit::AppSec::Events::V2.track_user_login_success(
    params['login'],
    params['user_id'],
    **params.fetch('metadata', {}).transform_keys(&:to_sym)
  )

  'OK'
end

post '/user_login_failure_event_v2' do
  require 'datadog/kit/appsec/events/v2'
  request.body.rewind
  params = JSON.parse(request.body.read)

  Datadog::Kit::AppSec::Events::V2.track_user_login_failure(
    params['login'],
    params.fetch('exists', 'false') == 'true',
    params.fetch('metadata', {}).transform_keys(&:to_sym)
  )

  'OK'
end

%i[get post options].each do |request_method|
  send(request_method, '/tag_value/:tag_value/:status_code') do
    event_value = params['tag_value']
    status_code = params['status_code']

    headers_from_query = request.query_string.split('&').map { |e| e.split('=') } || []
    headers_from_query.each do |key, value|
      response.headers[key] = value
    end

    if request.request_method == 'POST' && event_value.include?('payload_in_response_body')
      return json(payload: request.POST)
    end

    trace = Datadog::Tracing.active_trace
    trace.set_tag('appsec.events.system_tests_appsec_event.value', event_value)

    status status_code
    'Value tagged'
  end
end

get '/users' do
  user_id = request.params['user']

  Datadog::Kit::Identity.set_user(id: user_id)

  'Hello, user!'
end

get '/requestdownstream' do
  content_type :json

  uri = URI('http://localhost:7777/returnheaders')
  ext_request = nil
  ext_response = nil

  Net::HTTP.start(uri.host, uri.port) do |http|
    ext_request = Net::HTTP::Get.new(uri)

    ext_response = http.request(ext_request)
  end

  ext_response.body
end

get '/returnheaders' do
  content_type :json

  # Convert headers from Rack format to browser format

  headers = request.env.select { |k, _v| k.start_with?('HTTP_') }
  headers = headers.transform_keys { |k| k.sub(/^HTTP_/, '').split('_').map(&:capitalize).join('-') }

  headers.to_json
end

get '/sample_rate_route/:i' do
  'OK'
end

get '/api_security_sampling/:i' do
  'Hello!'
end

get '/api_security/sampling/:status' do
  status params['status'].to_i
  'OK'
end

ssrf_handler = lambda do
  url = URI.parse(request.params['domain'])
  url = "http://#{url}" unless url.scheme

  Faraday.get(url)

  'OK'
end
get '/rasp/ssrf', &ssrf_handler
post '/rasp/ssrf', &ssrf_handler

get '/flush' do
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

  'OK'
end
