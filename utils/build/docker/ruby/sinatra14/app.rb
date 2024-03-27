require 'pry'
require 'sinatra'
require "net/http"
require "uri"
require 'json'

require 'datadog/auto_instrument'

Datadog.configure do |c|
  c.diagnostics.debug = true

  unless c.respond_to?(:tracing)
    c.use :sinatra, service_name: (ENV['DD_SERVICE'] || 'sinatra')
  end
end

require 'rack/contrib/post_body_content_type_parser'
use Rack::PostBodyContentTypeParser

# Send non-web init event

if defined?(Datadog::Tracing)
  Datadog::Tracing.trace('init.service') { }
else
  Datadog.tracer.trace('init.service') { }
end

get '/' do
  'Hello, world!'
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
    repeats.times do |i|
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

  result.to_json
end

require 'datadog/kit/appsec/events'

get '/user_login_success_event' do
  Datadog::Kit::AppSec::Events.track_login_success(
    Datadog::Tracing.active_trace, user: {id: 'system_tests_user'}, metadata0: "value0", metadata1: "value1"
  )

  'Ok'
end

get '/user_login_failure_event' do
  Datadog::Kit::AppSec::Events.track_login_failure(
    Datadog::Tracing.active_trace, user_id: 'system_tests_user', user_exists: true, metadata0: "value0", metadata1: "value1"
  )

  'Ok'
end

get '/custom_event' do
  Datadog::Kit::AppSec::Events.track('system_tests_event', Datadog::Tracing.active_trace,  metadata0: "value0", metadata1: "value1")

  'Ok'
end

%i(get post options).each do |request_method|
  send(request_method, '/tag_value/:tag_value/:status_code') do
    if request_method == :post && params["tag_value"].include?('payload_in_response_body')
      content_type :json
      return {"payload":  request.POST }.to_json
    end

    trace = Datadog::Tracing.active_trace
    trace.set_tag("appsec.events.system_tests_appsec_event.value", params["tag_value"])

    status params["status_code"]
    headers request.params || {}

    'Value tagged'
  end
end

get '/users' do
  user_id = request.params["user"]

  Datadog::Kit::Identity.set_user(id: user_id)

  'Hello, user!'
end
