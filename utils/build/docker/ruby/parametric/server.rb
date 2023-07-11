# Add current folder to the search path
current_dir = Dir.pwd
$LOAD_PATH.unshift(current_dir) unless $LOAD_PATH.include?(current_dir)

require 'grpc'
require 'ddtrace'
require 'datadog/tracing/contrib/grpc/distributed/propagation' # Loads optional `Datadog::Tracing::Contrib::GRPC::Distributed`
require 'apm_test_client_services_pb'

Datadog.configure do |c|
  c.diagnostics.debug = true # When tests fail, ensure there's enough data to debug the failure.
  c.logger.instance = Logger.new(STDOUT) # Make sure logs are available for inspection from outside the container.
  c.tracing.instrument :http
end

puts Datadog.configuration.to_h

# Ensure output is always flushed, to prevent a forced shutdown from losing all logs.
STDOUT.sync = true
puts 'Loading server classes...'

class ServerImpl < APMClient::Service
  def start_span(start_span_args, _call)
    if start_span_args.http_headers.http_headers.size != 0 && (!start_span_args.origin.empty? || start_span_args.parent_id != 0)
      raise "cannot provide both http_headers and origin+parent_id for propagation: #{start_span_args.inspect}"
    end

    digest = if start_span_args.http_headers.http_headers.size != 0
               Datadog::Tracing::Contrib::GRPC::Distributed::Propagation.new.extract(start_span_args.http_headers.http_headers.map { |t| [t.key, t.value] }.to_h)
             elsif !start_span_args.origin.empty? || start_span_args.parent_id != 0
               # DEV: Parametric tests do not differentiate between a distributed span request from a span parenting request.
               # DEV: We have to consider the parent_id being present present and origin being absent as a span parenting request.
               # DEV: This is incorrect because a distributed request can have an absent origin.
               if !start_span_args.origin.empty?
                 Datadog::Tracing::TraceDigest.new(trace_origin: start_span_args.origin, span_id: start_span_args.parent_id)
               else
                 unless Datadog::Tracing.active_span&.id == start_span_args.parent_id
                   raise "active parent span id (#{Datadog::Tracing.active_span&.id}) does not match requested parent_id (#{start_span_args.parent_id})"
                 end
               end
             end

    span = Datadog::Tracing.trace(
      start_span_args.name,
      service: start_span_args.service,
      resource: start_span_args.resource,
      type: start_span_args.type,
      continue_from: digest,
    )

    StartSpanReturn.new(trace_id: Datadog::Tracing::Utils::TraceId.to_low_order(span.trace_id), span_id: span.id)
  end

  def finish_span(finish_span_args, _call)
    span = find_span(finish_span_args.id)

    span.finish

    FinishSpanReturn.new
  end

  def span_set_meta(span_set_meta_args, _call)
    span = find_span(span_set_meta_args.span_id)

    span.set_tag(
      span_set_meta_args.key,
      span_set_meta_args.value
    )

    SpanSetMetaReturn.new
  end

  def span_set_metric(span_set_metric_args, _call)
    span = find_span(span_set_metric_args.span_id)

    span.set_metric(
      span_set_metric_args.key,
      span_set_metric_args.value
    )

    SpanSetMetricReturn.new
  end

  def span_set_error(span_set_error_args, _call)
    span = find_span(span_set_error_args.span_id)

    span.set_error([
                     span_set_error_args.type,
                     span_set_error_args.message,
                     span_set_error_args.stack,
                   ])

    SpanSetErrorReturn.new
  end

  # HTTPRequestArgs.new.headers.http_headers
  def http_client_request(httprequest_args, _call)
    pp httprequest_args.to_h
    URI::HTTP
    url = URI(httprequest_args.url)
    # httprequest_args.body # TODO: fix me
    headers = httprequest_args.headers.http_headers.map{|x|[x.key, x.value] }.to_h

    puts '1'
    STDOUT.flush


    method = httprequest_args.to_h[:method]
    request_class = Net::HTTP.const_get(method.capitalize)
    request = request_class.new(url, headers).tap { |r| r.body = httprequest_args.body }

    response = Net::HTTP.start(url.hostname, url.port, use_ssl: url.scheme == 'https') do |http|
      http.request(request)
    end

    HTTPRequestReturn.new(status_code: response.code)
  end

  # alias httpclient_request httpclient_request

  def htt_pserver_request
    HTTPRequestArgs
    HTTPRequestReturn.new
  end

  def inject_headers(inject_headers_args, _call)
    find_span(inject_headers_args.span_id)

    env = {}
    Datadog::Tracing::Contrib::GRPC::Distributed::Propagation.new.inject!(Datadog::Tracing.active_trace.to_digest, env)

    tuples = env.map do |key, value|
      HeaderTuple.new(key:, value:)
    end

    InjectHeadersReturn.new(http_headers: DistributedHTTPHeaders.new(http_headers: tuples))
  end

  def flush_spans(flush_spans_args, _call)
    sleep 0.05 until Datadog.send(:components).tracer.writer.worker&.trace_buffer.empty?
    FlushSpansReturn.new
  end

  def flush_trace_stats(flush_trace_stats_args, _call)
    FlushTraceStatsReturn.new
  end

  # TODO: Implement these OTel methods
  # :otel_start_span, ::OtelStartSpanArgs, ::OtelStartSpanReturn
  # :otel_end_span, ::OtelEndSpanArgs, ::OtelEndSpanReturn
  # :otel_is_recording, ::OtelIsRecordingArgs, ::OtelIsRecordingReturn
  # :otel_span_context, ::OtelSpanContextArgs, ::OtelSpanContextReturn
  # :otel_set_status, ::OtelSetStatusArgs, ::OtelSetStatusReturn
  # :otel_set_name, ::OtelSetNameArgs, ::OtelSetNameReturn
  # :otel_set_attributes, ::OtelSetAttributesArgs, ::OtelSetAttributesReturn
  # :otel_flush_spans, ::OtelFlushSpansArgs, ::OtelFlushSpansReturn
  # :otel_flush_trace_stats, ::OtelFlushTraceStatsArgs, ::OtelFlushTraceStatsReturn

  def stop_tracer(stop_tracer_args, _call)
    Datadog.shutdown!
    StopTracerReturn.new
  end











  # The Ruby tracer holds spans on a per-Fiber basis.
  # To allow for `#start_span`/`#finish_span` pairs to work seemly,
  # the easiest way is to ensure all calls to this server execute in a single context.
  #
  # Because Fibers cannot be resumed across different threads, and this gRPC
  # server handles each request in a different thread, we are using the next best thing,
  # Threads, to ensure we are executing all requests to this server in a single thread.
  # This allows `ddtrace` to handle trace and span context natively.
  def initialize
    super

    @request_queue = Queue.new
    @return_queue = Queue.new

    @thread = Thread.new do
      loop do
        m, args = @request_queue.pop
        ret = public_send(m, *args)
        @return_queue.push(ret)
      rescue StandardError => e
        @return_queue.push(e)
      end
    end
  end

  # Wrap all public methods to ensure they execute in a single thread.
  public_instance_methods(false).each do |m|
    alias_method("wrapped_#{m}", m)
    define_method(m) do |*args|
      @request_queue.push ["wrapped_#{m}", args]
      res = @return_queue.pop

      if res.is_a?(Exception)
        res.message << ": #{res.backtrace}"
        raise res
      end

      res
    end
  end

  private

  def find_span(span_id)
    span = Datadog::Tracing.active_span
    raise 'Request span is not the active span' unless span && span.id == span_id

    span
  end
end

STDOUT.flush

port = ENV.fetch('APM_TEST_CLIENT_SERVER_PORT', 50051)
endpoint = "0.0.0.0:#{port}"
s = GRPC::RpcServer.new
s.add_http2_port(endpoint, :this_port_is_insecure)
GRPC.logger.info("... running insecurely on #{port}")

# Run this Ruby file with DEBUG=1 to start a debugging session.
Thread.new do
  sleep 0.01 # Wait for server to start

  # This is the gRPC client instance for this server
  client = APMClient::Stub.new(endpoint, :this_channel_is_insecure)

  puts "TIP: You cause use the `client` object to make gPRC requests."

  binding.irb

  exit(0)
end if ENV['DEBUG'] == '1'

puts 'Running gRPC server...'
STDOUT.flush
s.handle(ServerImpl.new())

# Runs the server with SIGHUP, SIGINT and SIGQUIT signal handlers to
#   gracefully shutdown.
# User could also choose to run server via call to run_till_terminated
s.run_till_terminated_or_interrupted([1, 'int', 'SIGQUIT'])
