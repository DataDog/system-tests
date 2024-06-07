# Add current folder to the search path
current_dir = Dir.pwd
$LOAD_PATH.unshift(current_dir) unless $LOAD_PATH.include?(current_dir)

require 'grpc'

# Support gem rename on both branches
begin
  require 'datadog'
  puts Datadog::VERSION::STRING
rescue LoadError
end
begin
  require 'ddtrace'
  puts DDTrace::VERSION::STRING
rescue LoadError
end

require 'datadog/tracing/contrib/grpc/distributed/propagation' # Loads optional `Datadog::Tracing::Contrib::GRPC::Distributed`
puts 'Loading server dependencies...'

require 'datadog/tracing/span_link'
require 'apm_test_client_services_pb'

# Only used for OpenTelemetry testing.
require 'opentelemetry/sdk'
require 'datadog/opentelemetry' # TODO: Remove when DD_TRACE_OTEL_ENABLED=true works out of the box for Ruby APM

OpenTelemetry::SDK.configure # Initialize OpenTelemetry

Datadog.configure do |c|
  # c.diagnostics.debug = true # When tests fail, ensure there's enough data to debug the failure.
  c.logger.instance = Logger.new(STDOUT) # Make sure logs are available for inspection from outside the container.
  c.tracing.instrument :http # Used for `http_client_request`
end

if Datadog::Core::Remote.active_remote
  # TODO: Remove this whole `if` condition if remote configuration is started by default.
  raise "Remote Configuration worker already started! Remove this check and `Datadog::Core::Remote.active_remote.start` below." if Datadog::Core::Remote.active_remote.started?
  Datadog::Core::Remote.active_remote.start
end

# Ensure output is always flushed, to prevent a forced shutdown from losing all logs.
STDOUT.sync = true
puts 'Loading server classes...'

class ServerImpl < APMClient::Service
  def start_span(start_span_args, _call)
    if start_span_args.http_headers.http_headers.size != 0 && (!start_span_args.origin.empty? || start_span_args.parent_id != 0)
      raise "cannot provide both http_headers and origin+parent_id for propagation: #{start_span_args.inspect}"
    end

    digest = if start_span_args.http_headers.http_headers.size != 0
               # Emulate how Rack headers concatenates header with duplicate values with a `, `.
               headers = start_span_args.http_headers.http_headers.group_by(&:key).map do |name, values|
                 [name, values.map(&:value).join(', ')]
               end
               extract_grpc_headers(headers)
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

    span.links = start_span_args.span_links.map do |link|
      parse_grpc_link(link)
    end if start_span_args.span_links.size > 0

    @dd_spans[span.id] = span
    @dd_traces[span.trace_id] = Datadog::Tracing.active_trace
    StartSpanReturn.new(trace_id: Datadog::Tracing::Utils::TraceId.to_low_order(span.trace_id), span_id: span.id)
  end

  def finish_span(finish_span_args, _call)
    span = find_span(finish_span_args.id)

    span.finish

    FinishSpanReturn.new
  end

  def get_trace_config(get_trace_config_args, _call)
    config = {}
    Datadog.configure do |c|
      config["dd_service"] = c.service || ""
      config["dd_trace_sample_rate"] = c.tracing.sampling.default_rate.to_s
      config["dd_trace_enabled"] = c.tracing.enabled.to_s
      config["dd_runtime_metrics_enabled"] = c.runtime_metrics.enabled.to_s # x
      config["dd_trace_propagation_style"] = c.tracing.propagation_style.join(",")
      config["dd_trace_debug"] = c.diagnostics.debug.to_s
      config["dd_env"] = c.env || ""
      config["dd_version"] = c.version || ""
      config["dd_tags"] = c.tags.nil? ? "" : c.tags.map { |k, v| "#{k}:#{v}" }.join(",")
    end
    GetTraceConfigReturn.new(config: config)
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

  def span_add_link(span_add_link_args, _call)
    link = parse_grpc_link(span_add_link_args.span_link)
    @dd_spans[span_add_link_args.span_id].links.push(link)
    SpanAddLinkReturn.new
  end

  def http_client_request(httprequest_args, _call)
    url = URI(httprequest_args.url)
    headers = httprequest_args.headers.http_headers.map{|x|[x.key, x.value] }.to_h
    method = httprequest_args.to_h[:method]

    request_class = Net::HTTP.const_get(method.capitalize)
    request = request_class.new(url, headers).tap { |r| r.body = httprequest_args.body }

    response = Net::HTTP.start(url.hostname, url.port, use_ssl: url.scheme == 'https') do |http|
      http.request(request)
    end

    HTTPRequestReturn.new(status_code: response.code)
  end

  # DEV: Defined in proto but not yet used in any test.
  def http_server_request(_httprequest_args, _call)
    raise NotImplementedError
  end

  def inject_headers(inject_headers_args, _call)
    find_span(inject_headers_args.span_id)

    env = {}
    if Datadog::Tracing::Contrib::GRPC.respond_to?(:inject)
      Datadog::Tracing::Contrib::GRPC.inject(Datadog::Tracing.active_trace.to_digest, env)
    else
      Datadog::Tracing::Contrib::GRPC::Distributed::Propagation.new.inject!(Datadog::Tracing.active_trace.to_digest, env)
    end

    tuples = env.map do |key, value|
      HeaderTuple.new(key:, value:)
    end

    InjectHeadersReturn.new(http_headers: DistributedHTTPHeaders.new(http_headers: tuples))
  end

  def flush_spans(flush_spans_args, _call)
    wait_for_flush(5)

    FlushSpansReturn.new
  end

  def flush_trace_stats(flush_trace_stats_args, _call)
    FlushTraceStatsReturn.new
  end

  OTEL_SPAN_KIND = {
    1 => :internal,
    2 => :server,
    3 => :client,
    4 => :producer,
    5 => :consumer,
  }

  def otel_start_span(otel_start_span_args, _call)
    headers = header_hash(otel_start_span_args.http_headers)
    if !headers.empty?
      parent_context = OpenTelemetry.propagation.extract(headers)
    elsif otel_start_span_args.parent_id != 0
      parent_span = find_otel_span(otel_start_span_args.parent_id)
      parent_context = OpenTelemetry::Trace.context_with_span(parent_span)
    end

    otel_links = otel_start_span_args.span_links.map do |link|
      dd_link = parse_grpc_link(link)
      dd_link_to_otel(dd_link)
    end

    span = otel_tracer.start_span(
      otel_start_span_args.name,
      with_parent: parent_context,
      attributes: parse_grpc_attributes(otel_start_span_args.attributes),
      start_timestamp: otel_correct_time(otel_start_span_args.timestamp),
      kind: OTEL_SPAN_KIND[otel_start_span_args.span_kind],
      links: otel_links
    )

    context = span.context

    @otel_spans[otel_span_id_to_dd(context.span_id)] = span

    OtelStartSpanReturn.new(span_id: otel_span_id_to_dd(context.span_id), trace_id: otel_trace_id_to_dd(context.trace_id))
  end

  def otel_end_span(otel_end_span_args, _call)
    span = find_otel_span(otel_end_span_args.id)
    span.finish(end_timestamp: otel_correct_time(otel_end_span_args.timestamp))

    OtelEndSpanReturn.new
  end

  def otel_is_recording(otel_is_recording_args, _call)
    span = find_otel_span(otel_is_recording_args.span_id)
    OtelIsRecordingReturn.new(is_recording: span.recording?)
  end

  def otel_span_context(otel_span_context_args, _call)
    span = find_otel_span(otel_span_context_args.span_id)
    context = span.context

    OtelSpanContextReturn.new(
      span_id: format('%016x', otel_span_id_to_dd(context.span_id)),
      trace_id: format('%032x', otel_trace_id_to_dd(context.trace_id)),
      trace_flags: context.trace_flags.sampled? ? '01' : '00',
      trace_state: context.tracestate.to_s,
      remote: context.remote?,
    )
  end

  def otel_add_link(otel_add_link_args, _call)
    span = find_otel_span(otel_add_link_args.span_id)
    dd_link = parse_grpc_link(otel_add_link_args.link)
    otel_link = dd_link_to_otel(dd_link)
    span.add_link(otel_link)
  end

  def otel_set_status(otel_set_status_args, _call)
    span = find_otel_span(otel_set_status_args.span_id)

    span.status = OpenTelemetry::Trace::Status.public_send(
      otel_set_status_args.code.downcase,
      otel_set_status_args.description
    )

    OtelSetStatusReturn.new
  end

  def otel_set_name(otel_set_name_args, _call)
    span = find_otel_span(otel_set_name_args.span_id)
    span.name = otel_set_name_args.name
    OtelSetNameReturn.new
  end

  def otel_set_attributes(otel_set_attributes_args, _call)
    span = find_otel_span(otel_set_attributes_args.span_id
    )
    parse_grpc_attributes(otel_set_attributes_args.attributes).each do |key, value|
      span.set_attribute(key, value)
    end

    OtelSetAttributesReturn.new
  end

  def otel_flush_spans(otel_flush_spans_args, _call)
    success = wait_for_flush(otel_flush_spans_args.seconds)

    OtelFlushSpansReturn.new(success: success)
  end

  def otel_flush_trace_stats(_otel_flush_trace_stats_args, _call)
    OtelFlushTraceStatsReturn.new
  end

  def stop_tracer(stop_tracer_args, _call)
    Datadog.shutdown!
    StopTracerReturn.new

    @otel_spans.clear
    @dd_spans.clear
    @dd_traces.clear
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

    # Lists of Span objects that allow for retrieving spans in-between API calls.
    @otel_spans = {}
    @dd_spans = {}
    @dd_traces = {}
  end

  # Wrap all public methods to ensure they execute in a single thread.
  public_instance_methods(false).each do |m|
    alias_method("wrapped_#{m}", m)
    define_method(m) do |*args|
      @request_queue.push ["wrapped_#{m}", args]
      res = @return_queue.pop

      if res.is_a?(Exception)
        # Include the backtrace in the error returned to the test suite.
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

  def wait_for_flush(seconds)
    return true unless (worker = Datadog.send(:components).tracer.writer.worker)

    count = 0
    sleep_time = seconds / 100.0
    until worker.trace_buffer&.empty?
      sleep sleep_time
      count += 1
      return false if count >= 100
    end

    true
  end

  def header_hash(http_headers)
    http_headers.http_headers.map { |t| [t.key, t.value] }.to_h
  end

  def find_otel_span(id)
    span = @otel_spans[id]
    raise "Requested span #{id} not found. All spans: #{@otel_spans.map{|s|s.context.span_id}}" unless span

    span
  end

  # Convert OTel's binary representation to an unsigned 64-bit Integer.
  def otel_span_id_to_dd(span_id)
    span_id.unpack1('Q')
  end

  def otel_trace_id_to_dd(trace_id)
    trace_id.unpack1('H*').to_i(16)
  end

  # Convert an unsigned 64 bit integer to OTel's binary representation.
  def i_to_otel_span_id(span_id)
    [span_id].pack('Q')
  end

  # Convert an unsigned bignum to OTel's binary representation.
  def i_to_otel_trace_id(trace_id)
    [trace_id.to_s(16)].pack('H*')
  end

  # OTel system tests provide times in microseconds, but Ruby OTel
  # measures time in seconds (Float).
  def otel_correct_time(microseconds)
    microseconds &./ 1000000.0
  end

  # Convert Protobuf attributes to native Ruby objects
  # e.g. `Attributes.new(key_vals: { my_key:ListVal.new(val: [AttrVal.new(bool_val: true)])})`
  def parse_grpc_attributes(attributes)
    attributes.key_vals.map do |k, v|
      [k.to_s, v.val.map do |union|
        union[union.val.to_s]
      end.yield_self do |value|
        # Flatten array of 1 element into a scalar.
        # This is due to the gRPC API not differentiating between a
        # single value and an array with 1 value
        if value.size == 1
          value[0]
        else
          value
        end
      end]
    end.to_h
  end

  def parse_grpc_link(link)
    link_dg = if link.http_headers != nil && link.http_headers.http_headers.size != nil
                headers = link.http_headers.http_headers.group_by(&:key).map do |name, values|
                            [name, values.map(&:value).join(', ')]
                          end
                extract_grpc_headers(headers)
              elsif @dd_spans.key?(link.parent_id)
                span_op = @dd_spans[link.parent_id]
                trace_op = @dd_traces[span_op.trace_id]
                Datadog::Tracing::TraceDigest.new(
                  span_id: span_op.id,
                  trace_id: span_op.trace_id,
                  trace_sampling_priority: trace_op.sampling_priority,
                  trace_flags: trace_op.sampling_priority && trace_op.sampling_priority > 0 ? 1 : 0,
                  trace_state: trace_op.trace_state
                )
              else
                raise "Span id in #{link} not found in span list: #{@dd_spans}"
              end
    Datadog::Tracing::SpanLink.new(
      link_dg,
      attributes: parse_grpc_attributes(link.attributes)
    )
  end

  def dd_link_to_otel(dd_link)
    OpenTelemetry::Trace::Link.new(
        OpenTelemetry::Trace::SpanContext.new(
          trace_id: i_to_otel_trace_id(dd_link.trace_id),
          span_id: i_to_otel_span_id(dd_link.span_id),
          trace_flags: OpenTelemetry::Trace::TraceFlags.from_byte(dd_link.trace_flags),
          tracestate: OpenTelemetry::Trace::Tracestate.from_string(dd_link.trace_state)
        ),
        dd_link.attributes
      )
  end

  def otel_tracer
    OpenTelemetry.tracer_provider.tracer('otel-tracer')
  end

  def extract_grpc_headers(headers)
    if Datadog::Tracing::Contrib::GRPC.respond_to?(:extract)
      Datadog::Tracing::Contrib::GRPC.extract(headers.to_h)
    else
      Datadog::Tracing::Contrib::GRPC::Distributed::Propagation.new.extract(headers.to_h)
    end
  end
end

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
