require 'json'

require 'datadog/kit/appsec/events'
require 'rdkafka'

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
      "status_code": response.code,
      "request_headers": request.each_header.to_h,
      "response_headers": response.each_header.to_h,
    }

    render json: result
  end

  def tag_value
    event_value = params[:tag_value]
    status_code = params[:status_code]

    headers = request.query_string.split('&').map {|e | e.split('=')} || []
    headers.each do |key, value|
      response.headers[key] = value
    end

    if request.method == "POST" && event_value.include?('payload_in_response_body')
      render json: { payload: request.POST }
      return
    end

    trace = Datadog::Tracing.active_trace
    trace.set_tag("appsec.events.system_tests_appsec_event.value", event_value)

    render plain: 'Value tagged', status: status_code
  end

  def users
    user_id = request.params["user"]

    Datadog::Kit::Identity.set_user(id: user_id)

    render plain: 'Hello, user!'
  end

  def kafka_produce
    config = {
      :"bootstrap.servers" => "kafka:9092",
      :"client.id" => "system-tests-client-producer",
      :"group.id" => "system-tests-group",
    }
    topic = request.params["topic"]
    producer = Rdkafka::Config.new(config).producer
    stop = false
    while stop == false
      delivery_handles = []
      begin
        Datadog::Tracing.trace('kafka_produce') do |span|
          delivery_handles << producer.produce(
            topic:   topic,
            payload: "Hello, world!",
          )
          # This has to be done manually for now, because ruby does not add the topic
          # to the span at all
          span.set_tag("span.kind", "producer")
          span.set_tag("kafka.topic", topic)
          stop = true
        end
      rescue Rdkafka::BaseError
      end
      delivery_handles.each(&:wait)
    end
    producer.close

    render plain: "Done"
  end


  def kafka_consume
    config = {
      :"bootstrap.servers" => "kafka:9092",
      :"client.id" => "system-tests-client-consumer",
      :"group.id" => "system-tests-group",
      :"auto.offset.reset" => "earliest",
    }
    topic = request.params["topic"]
    consumer = Rdkafka::Config.new(config).consumer
    consumer.subscribe(topic)
    begin
      consumer.each do |message|
        if not message.nil?
          Datadog::Tracing.trace('kafka_consume') do |span|
            span.set_tag("span.kind", "consumer")
            span.set_tag("kafka.topic", topic)
          end
          break
        end
      end
    rescue Exception => e
      puts "An error has occurred while consuming messages from Kafka: #{e}"
    ensure
      consumer.close
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

  def handle_path_params
    render plain: 'OK'
  end
end
