require 'datadog/kit/appsec/events'
require 'rdkafka'
require 'aws-sdk-sqs'
require 'aws-sdk-sns'

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

  AWS_FAKE_ENDPOINT = 'http://localstack-main:4566'
  AWS_SQS_FAKE_ENDPOINT = "http://elasticmq:9324"
  AWS_REGION = 'us-east-1'

  def sqs_consume
    client = Aws::SQS::Client.new(endpoint: AWS_SQS_FAKE_ENDPOINT, region: AWS_REGION)

    queue_url = client.create_queue(queue_name: request.params["queue"]).queue_url
    response = client.receive_message(queue_url: queue_url, wait_time_seconds: request.params["timeout"].to_i)

    if response.messages.empty?
      render plain: 'No messages', status: 400
      return
    end

    message = response.messages[0]
    body = message.body
    Rails.logger.info("Consumed the SQS message: #{body}")

    render({ message: body }, 200)
  end

  def sqs_produce
    client = Aws::SQS::Client.new(endpoint: AWS_SQS_FAKE_ENDPOINT, region: AWS_REGION)

    queue_url = client.create_queue(queue_name: request.params["queue"]).queue_url
    client.send_message(queue_url: queue_url, message_body: "Hello, world!")

    render plain: "Done"
  end


  def sns_produce
    sqs = Aws::SQS::Client.new(endpoint: AWS_FAKE_ENDPOINT, region: AWS_REGION)
    sns = Aws::SNS::Client.new(endpoint: AWS_FAKE_ENDPOINT, region: AWS_REGION)

    queue_name = request.params["queue"]
    topic_name = request.params["topic"]

    topic_arn = sns.create_topic(name: topic_name).topic_arn
    sqs_url = sqs.create_queue(queue_name: queue_name).queue_url

    url_parts = sqs_url.split("/")
    sqs_arn = "arn:aws:sqs:#{AWS_REGION}:#{url_parts[-2]}:#{url_parts[-1]}"

    sns.subscribe(topic_arn: topic_arn,
                  protocol: "sqs",
                  endpoint: sqs_arn)

    Rails.logger.info("[SNS->SQS] Created SNS Topic: #{topic_arn} and SQS Queue: #{sqs_url}")

    sns.publish(topic_arn: topic_arn, message: 'Hello from Ruby SNS -> SQS')

    Rails.logger.info("[SNS->SQS] Ruby SNS messaged published successfully")

    render plain: "SNS Produce ok"
  end

  def sns_consume
    region = "us-east-1"
    sqs = Aws::SQS::Client.new(endpoint: AWS_FAKE_ENDPOINT, region: region)

    queue_name = request.params["queue"]
    queue_url = sqs.get_queue_url(queue_name: queue_name).queue_url

    consumed_message = nil
    start_time = Time.now

    timeout = request.params["timeout"].to_i
    while Time.now - start_time < timeout
      begin
        response = sqs.receive_message(queue_url: queue_url)
        if response.messages.any?
          message = response.messages[0]
          consumed_message = message.body
          Rails.logger.info("[SNS->SQS] Consumed the following: " + consumed_message)

          break if consumed_message
        end
      rescue StandardError => e
        Rails.logger.warning("[SNS->SQS] " + e.to_s)
      end
      sleep(0.1)
    end

    if consumed_message.nil?
      render plain: 'No messages', status: 400
      return
    end

    render({ message: consumed_message }, 200)
  end
end
