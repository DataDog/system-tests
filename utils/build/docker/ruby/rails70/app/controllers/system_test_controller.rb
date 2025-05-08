require 'json'

require 'datadog/kit/appsec/events'
require 'kafka'
require 'opentelemetry'

class SystemTestController < ApplicationController
  skip_before_action :verify_authenticity_token

  def root
    render plain: 'Hello, world!'
  end

  def healthcheck
    gemspec = Gem.loaded_specs['datadog'] || Gem.loaded_specs['ddtrace']
    version = gemspec.version.to_s
    version = "#{version}-dev" unless gemspec.source.is_a?(Bundler::Source::Rubygems)
    render json: {
      status: 'ok',
      library: {
        name: 'ruby',
        version: version
      }
    }
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
      "status_code": response.code,
      "request_headers": request.each_header.to_h,
      "response_headers": response.each_header.to_h,
    }

    render json: result
  end

  def log_library
    message = params[:msg]
    Rails.logger.info(message)
    render plain: 'OK'
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

  def kafka_produce
    kafka = Kafka.new(
      seed_brokers: ["kafka:9092"],
      client_id: "system-tests-client-producer",
    )
    producer = kafka.producer
    topic = request.params["topic"] || "DistributedTracing"
    begin
      producer.produce(
        "Hello, world!",
        topic:   topic,
      )
      producer.deliver_messages
      producer.shutdown
    rescue Exception => e
      puts "An error has occurred while consuming messages from Kafka: #{e}"
    end
    render plain: "Done"
  end


  def kafka_consume
    kafka = Kafka.new(
      seed_brokers: ["kafka:9092"],
      client_id: "system-tests-client-consumer",
      socket_timeout: 20,
    )
    topic = request.params["topic"] || "DistributedTracing"
    begin
      kafka.each_message(topic: topic) do |message|
        if not message.nil?
          puts "Received message: #{message.value}"
          break
        end
      end
    rescue Exception => e
      puts "An error has occurred while consuming messages from Kafka: #{e}"
    end
    render plain: "Done"
  end

  def request_downstream
    uri = URI('http://localhost:7777/returnheaders')
    ext_request = nil
    ext_response = nil

    Net::HTTP.start(uri.host, uri.port) do |http|
      ext_request = Net::HTTP::Get.new(uri)

      ext_response = http.request(ext_request)
    end

    render json: ext_response.body, content_type: 'application/json'
  end

  def return_headers
    request_headers = request.headers.each.to_h.select do |k, _v|
      k.start_with?('HTTP_') || k == 'CONTENT_TYPE' || k == 'CONTENT_LENGTH'
    end
    request_headers = request_headers.transform_keys do |k|
      k.sub(/^HTTP_/, '').split('_').map(&:capitalize).join('-')
    end
    render json: JSON.generate(request_headers), content_type: 'application/json'
  end

  def otel_drop_in_default_propagator_extract
    # The extract operation succeeds with a custom OpenTelemetry propagator, but not with the default one.
    # To see this, uncomment the next line, and use that propagator to do the context extraction
    # propagator = OpenTelemetry::Context::Propagation::CompositeTextMapPropagator.compose_propagators([OpenTelemetry::Trace::Propagation::TraceContext.text_map_propagator, OpenTelemetry::Baggage::Propagation.text_map_propagator])
    context = OpenTelemetry.propagation.extract(request.headers)

    span_context = OpenTelemetry::Trace.current_span(context).context

    baggage = OpenTelemetry::Baggage.raw_entries()
    baggage_str = ""
    baggage.each_pair do |key, value|
      baggage_str << value << ','
    end
    baggage_str.chop!

    result = {}
    result["trace_id"] = span_context.hex_trace_id.from(16).to_i(16)
    result["span_id"] = span_context.hex_span_id.to_i(16)
    result["tracestate"] = span_context.tracestate.to_s
    result["baggage"] = baggage_str

    render json: JSON.generate(result), content_type: 'application/json'
  end

  def otel_drop_in_default_propagator_inject
    headers = {}
    OpenTelemetry.propagation.inject(headers)
    render json: JSON.generate(headers), content_type: 'application/json'
  end

  def handle_path_params
    render plain: 'OK'
  end

  def sample_rate_route
    render plain: 'OK'
  end
end
