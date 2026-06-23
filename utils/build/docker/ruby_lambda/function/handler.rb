# frozen_string_literal: true

require 'uri'
require 'json'
require 'net/http'
require 'datadog/lambda'
require 'datadog/appsec'
require 'datadog/kit/appsec/events'

Datadog::Lambda.configure_apm do |c|
  c.tracing.instrument :http
end

MAGIC_SESSION_KEY = 'random_session_id'
TRACK_CUSTOM_APPSEC_EVENT_NAME = 'system_tests_appsec_event'
TRACK_USER = 'system_tests_user'

def handler(event:, context:)
  return version_info if event['healthcheck']

  Datadog::Lambda.wrap(event, context) { route_request(event) }
end

def route_request(event)
  path = event['path'] || event['rawPath'] || '/'
  method = event['httpMethod'] || event.dig('requestContext', 'http', 'method') || 'GET'
  query = event['queryStringParameters'] || {}
  headers = event['headers'] || {}
  body = event['body']

  case path
  when '/'
    response(200, "Hello, World!\n", 'Content-Type' => 'text/plain')
  when '/healthcheck'
    json_response(200, version_info)
  when '/headers'
    response(200, 'OK', 'Content-Type' => 'text/plain', 'Content-Language' => 'en-US')
  when %r{\A/waf(?:/.*)?\z}
    response(200, "Hello, World!\n", 'Content-Type' => 'text/plain')
  when %r{\A/params(?:/.*)?\z}
    response(200, "Hello, World!\n", 'Content-Type' => 'text/plain')
  when %r{\A/tag_value/([^/]+)/(\d+)\z}
    tag_value = Regexp.last_match(1)
    status_code = Regexp.last_match(2).to_i

    handle_tag_value(tag_value, status_code, method, query, body)
  when '/user_login_success_event'
    handle_user_login_success
  when '/session/new'
    handle_session_new
  when '/users'
    handle_users(query)
  when %r{\A/rasp/lfi\z}
    handle_rasp_lfi(method, query, body)
  when %r{\A/rasp/ssrf\z}
    handle_rasp_ssrf(method, query, body)
  when %r{\A/rasp/sqli\z}
    handle_rasp_sqli(method, query, body)
  when '/external_request'
    handle_external_request(method, query, headers, body)
  else
    response(404, 'Not Found', 'Content-Type' => 'text/plain')
  end
end

def handle_tag_value(tag_value, status_code, method, query, body)
  span = Datadog::Tracing.active_span
  span&.set_tag('appsec.events.system_tests_appsec_event.value', tag_value)

  Datadog::Kit::AppSec::Events.track(TRACK_CUSTOM_APPSEC_EVENT_NAME, span, value: tag_value)

  response_headers = query || {}

  if method == 'POST' && tag_value.start_with?('payload_in_response_body')
    form_data = URI.decode_www_form(body || '').to_h
    json_response(status_code, { payload: form_data }, **response_headers)
  else
    response_headers.merge!('Content-Type' => 'text/plain')
    response(status_code, 'Value tagged', response_headers)
  end
rescue StandardError
  response(200, 'Value tagged', 'Content-Type' => 'text/plain')
end

def handle_user_login_success
  Datadog::Kit::Identity.set_user(
    Datadog::Tracing,
    id: TRACK_USER,
    email: 'usr.email',
    name: 'usr.name'
  )
  response(200, 'OK', 'Content-Type' => 'text/plain')
rescue StandardError
  response(200, 'OK', 'Content-Type' => 'text/plain')
end

def handle_session_new
  {
    'statusCode' => 200,
    'body' => MAGIC_SESSION_KEY,
    'headers' => { 'Content-Type' => 'text/plain' },
    'multiValueHeaders' => {
      'Set-Cookie' => ["session_id=#{MAGIC_SESSION_KEY}; Path=/; HttpOnly"]
    }
  }
end

def handle_users(query)
  user = query['user'] || ''
  Datadog::Kit::Identity.set_user(
    Datadog::Tracing,
    id: user,
    email: 'usr.email',
    name: 'usr.name',
    session_id: 'usr.session_id',
    role: 'usr.role',
    scope: 'usr.scope'
  )
  response(200, 'OK', 'Content-Type' => 'text/plain')
rescue StandardError
  response(200, 'OK', 'Content-Type' => 'text/plain')
end

def handle_rasp_lfi(method, query, body)
  file = retrieve_arg('file', method, query, body)
  return response(400, 'missing file parameter', 'Content-Type' => 'text/plain') unless file

  begin
    size = File.size(file)
    response(200, "#{file} open with #{size} bytes", 'Content-Type' => 'text/plain')
  rescue => e
    response(200, "#{file} could not be open: #{e}", 'Content-Type' => 'text/plain')
  end
end

def handle_rasp_ssrf(method, query, body)
  domain = retrieve_arg('domain', method, query, body)
  return response(400, 'missing domain parameter', 'Content-Type' => 'text/plain') unless domain

  url = "http://#{domain}"
  begin
    uri = URI.parse(url)
    res = Net::HTTP.get_response(uri)
    response(200, "url #{url} open with #{res.body&.length || 0} bytes", 'Content-Type' => 'text/plain')
  rescue => e
    response(200, "url #{url} could not be open: #{e}", 'Content-Type' => 'text/plain')
  end
end

def handle_rasp_sqli(method, query, body)
  user_id = retrieve_arg('user_id', method, query, body)
  return response(400, 'missing user_id parameter', 'Content-Type' => 'text/plain') unless user_id

  response(200, "DB request with 0 results", 'Content-Type' => 'text/plain')
end

def handle_external_request(method, query, headers, body)
  status = query&.delete('status') || '200'
  url_extra = query&.delete('url_extra') || ''
  full_url = "http://internal_server:8089/mirror/#{status}#{url_extra}"

  uri = URI.parse(full_url)
  http = Net::HTTP.new(uri.host, uri.port)
  request = case method
            when 'POST' then Net::HTTP::Post.new(uri)
            when 'PUT' then Net::HTTP::Put.new(uri)
            else Net::HTTP::Get.new(uri)
            end

  query&.each { |k, v| request[k] = v }
  request.body = body if body

  res = http.request(request)
  json_response(200, {
    status: res.code.to_i,
    headers: res.each_header.to_h,
    payload: JSON.parse(res.body)
  })
rescue => e
  response(500, "External request failed: #{e}", 'Content-Type' => 'text/plain')
end

def retrieve_arg(key, method, query, body)
  case method
  when 'GET'
    query&.fetch(key, nil)
  when 'POST'
    return nil unless body

    form_arg(body, key) || json_arg(body, key)
  end
end

def form_arg(body, key)
  URI.decode_www_form(body).to_h[key]
rescue StandardError
  nil
end

def json_arg(body, key)
  data = JSON.parse(body)
  data[key] if data.is_a?(Hash)
rescue StandardError
  nil
end

def version_info
  {
    'status' => 'ok',
    'library' => {
      'name' => 'ruby_lambda',
      'version' => Datadog::Lambda::VERSION::STRING
    }
  }
end

def response(status_code, body, headers = {})
  {
    'statusCode' => status_code,
    'body' => body,
    'headers' => headers
  }
end

def json_response(status_code, data, **extra_headers)
  headers = {'Content-Type' => 'application/json'}.merge!(extra_headers)

  {
    'statusCode' => status_code,
    'body' => data.is_a?(String) ? data : JSON.generate(data),
    'headers' => headers
  }
end
