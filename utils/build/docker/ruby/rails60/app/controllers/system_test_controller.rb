require 'datadog/kit/appsec/events'

class SystemTestController < ApplicationController
  skip_before_action :verify_authenticity_token

  def root
    render plain: 'Hello, world!'
  end

  def waf
    render plain: 'Hello, world!'
  end

  def handle_path_params
    render plain: 'Hello, world!'
  end

  def generate_spans
    begin
      repeats = Integer(request.params['repeats'] || 0)
      garbage = Integer(request.params['garbage'] || 0)
    rescue ArgumentError
      render plain: 'bad request', status: 400
    else
      repeats.times do |i|
        Datadog::Tracing.trace('repeat-#{i}') do |span|
          garbage.times do |j|
            span.set_tag("garbage-#{j}", "#{j}")
          end
        end
      end
    end

    render plain: 'Generated #{repeats} spans with #{garbage} garbage tags'
  end

  def test_headers
    response.set_header('Content-Type', 'text/plain')
    response.set_header('Content-Length', '15')
    response.set_header('Content-Language', 'en-US')

    render plain: 'Hello, headers!'
  end

  def identify
    trace = Datadog::Tracing.active_trace
    trace.set_tag('usr.id', 'usr.id')
    trace.set_tag('usr.name', 'usr.name')
    trace.set_tag('usr.email', 'usr.email')
    trace.set_tag('usr.session_id', 'usr.session_id')
    trace.set_tag('usr.role', 'usr.role')
    trace.set_tag('usr.scope', 'usr.scope')

    render plain: 'Hello, world!'
  end


  def status
    render plain: "Ok", status: params[:code]
  end

  def make_distant_call
    url = params[:url]
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

    render json: result
  end

  def user_login_success_event
    Datadog::Kit::AppSec::Events.track_login_success(
      Datadog::Tracing.active_trace, user: {id: 'system_tests_user'}, metadata0: "value0", metadata1: "value1"
    )

    render plain: 'Hello, world!'
  end

  def user_login_failure_event
    Datadog::Kit::AppSec::Events.track_login_failure(
      Datadog::Tracing.active_trace, user_id: 'system_tests_user', user_exists: true, metadata0: "value0", metadata1: "value1"
    )

    render plain: 'Hello, world!'
  end

  def custom_event
    Datadog::Kit::AppSec::Events.track('system_tests_event', Datadog::Tracing.active_trace,  metadata0: "value0", metadata1: "value1")

    render plain: 'Hello, world!'
  enddef user_login_success_event
    Datadog::Kit::AppSec::Events.track_login_success(
      Datadog::Tracing.active_trace, user: {id: 'system_tests_user'}, metadata0: "value0", metadata1: "value1"
    )

    render plain: 'Hello, world!'
  end

  def user_login_failure_event
    Datadog::Kit::AppSec::Events.track_login_failure(
      Datadog::Tracing.active_trace, user_id: 'system_tests_user', user_exists: true, metadata0: "value0", metadata1: "value1"
    )

    render plain: 'Hello, world!'
  end

  def custom_event
    Datadog::Kit::AppSec::Events.track('system_tests_event', Datadog::Tracing.active_trace,  metadata0: "value0", metadata1: "value1")

    render plain: 'Hello, world!'
  end

  def tag_value
    headers = request.query_string.split('&').map {|e | e.split('=')} || []
    event_value = params[:key]
    status_code = params[:status_code]

    trace = Datadog::Tracing.active_trace
    trace.set_tag("appsec.events.system_tests_appsec_event.value", event_value)

    headers.each do |key, value|
      response.set_header(key, value)
    end

    render plain: 'Value tagged', status: status_code
  end
end
