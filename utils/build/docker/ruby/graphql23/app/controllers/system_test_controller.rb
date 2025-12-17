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

  def read_file
    render plain: File.read(params[:file])
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
      "status_code": response.code.to_i,
      "request_headers": request.each_header.to_h,
      "response_headers": response.each_header.to_h,
    }

    render json: result
  end

  def tag_value
    event_value = params[:tag_value]
    status_code = params[:status_code]

    if request.method == "POST" && event_value.include?('payload_in_response_body')
      render json: { payload: request.POST }
      return
    end

    headers = request.query_string.split('&').map {|e | e.split('=')} || []

    trace = Datadog::Tracing.active_trace
    trace.set_tag("appsec.events.system_tests_appsec_event.value", event_value)

    headers.each do |key, value|
      response.set_header(key, value)
    end

    render plain: 'Value tagged', status: status_code
  end

  def users
    user_id = request.params["user"]

    Datadog::Kit::Identity.set_user(id: user_id)

    render plain: 'Hello, user!'
  end

  def login
    request.env["devise.allow_params_authentication"] = true

    sdk_event = request.params[:sdk_event]
    sdk_user = request.params[:sdk_user]
    sdk_email = request.params[:sdk_mail]
    sdk_exists = request.params[:sdk_user_exists]

    if sdk_exists
      sdk_exists = sdk_exists == "true"
    end

    result = request.env['warden'].authenticate({ scope: Devise.mappings[:user].name })

    if sdk_event === 'failure' && sdk_user
      metadata = {}
      metadata[:email] = sdk_email if sdk_email
      Datadog::Kit::AppSec::Events.track_login_failure(user_id: sdk_user, user_exists: sdk_exists, **metadata)
    elsif sdk_event === 'success' && sdk_user
      user = {}
      user[:id] = sdk_user
      user[:email] = sdk_email if sdk_email
      Datadog::Kit::AppSec::Events.track_login_success(user: user)
    end

    unless result
      render plain: '', status: 401
      return
    end


    render plain: 'Hello, world!'
  end
end
