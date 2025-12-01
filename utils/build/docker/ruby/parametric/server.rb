require 'rack'
require 'webrick'
require 'rack/handler/webrick'
require 'json'

# Add current folder to the search path
current_dir = Dir.pwd
$LOAD_PATH.unshift(current_dir) unless $LOAD_PATH.include?(current_dir)

# Support gem rename on both branches
begin
  require 'datadog'
  puts Datadog::VERSION::STRING
rescue LoadError
  require 'ddtrace'
  puts DDTrace::VERSION::STRING
end

require 'datadog/tracing/contrib/grpc/distributed/propagation' # Loads optional `Datadog::Tracing::Contrib::GRPC::Distributed`
puts 'Loading server dependencies...'

require 'datadog/tracing/span_link'

require 'datadog/tracing/diagnostics/environment_logger'

# Only used for OpenTelemetry testing.
require 'opentelemetry/sdk'
require 'datadog/opentelemetry' # TODO: Remove when DD_TRACE_OTEL_ENABLED=true works out of the box for Ruby APM

OpenTelemetry::SDK.configure # Initialize OpenTelemetry

Datadog.configure do |c|
  if ENV['DD_TRACE_DEBUG'].nil?
    # If DD_TRACE_DEBUG is set do not override this configuration.
    c.diagnostics.debug = true # When tests fail, ensure there's enough data to debug the failure.
  end
  c.logger.instance = Logger.new(STDOUT) # Make sure logs are available for inspection from outside the container.
end

if Datadog::Core::Remote.active_remote
  # TODO: Remove this whole `if` condition if remote configuration is started by default.
  if Datadog::Core::Remote.active_remote.started?
    raise 'Remote Configuration worker already started! Remove this check and `Datadog::Core::Remote.active_remote.start` below.'
  end

  Datadog::Core::Remote.active_remote.start
end

def otel_tracer
  OpenTelemetry.tracer_provider.tracer('otel-tracer')
end

OTEL_SPAN_KIND = {
  0 => :internal,
  1 => :server,
  2 => :client,
  3 => :producer,
  4 => :consumer
}

# Ensure output is always flushed, to prevent a forced shutdown from losing all logs.
STDOUT.sync = true
puts 'Loading server classes...'

DD_SPANS = {}
DD_TRACES = {}
DD_DIGEST = {}
OTEL_SPANS = {}

HeaderTuple = Struct.new(:key, :value, keyword_init: true)

class StartSpanArgs
  attr_accessor :parent_id, :name, :service, :type, :resource, :span_tags

  def initialize(params)
    @parent_id = params['parent_id']
    @name = params['name']
    @service = params['service']
    @type = params['type']
    @resource = params['resource']
    @span_tags = params['span_tags']
  end
end

class StartSpanReturn
  attr_accessor :span_id, :trace_id

  def initialize(span_id, trace_id)
    @span_id = span_id
    @trace_id = trace_id
  end

  def to_json(*_args)
    { span_id: @span_id, trace_id: @trace_id }.to_json
  end
end

class SpanFinishArgs
  attr_accessor :span_id

  def initialize(params)
    @span_id = params['span_id']
  end
end

class SpanFinishReturn
  def to_json(*_args)
    {}.to_json
  end
end

class TraceConfigReturn
  attr_accessor :config

  def initialize(config)
    @config = config
  end

  def to_json(*_args)
    { config: @config }.to_json
  end
end

class SpanSetMetaArgs
  attr_accessor :span_id, :key, :value

  def initialize(params)
    @span_id = params['span_id']
    @key = params['key']
    @value = params['value']
  end
end

class SpanSetMetaReturn
  def to_json(*_args)
    {}.to_json
  end
end

class SpanSetMetricArgs
  attr_accessor :span_id, :key, :value

  def initialize(params)
    @span_id = params['span_id']
    @key = params['key']
    @value = params['value']
  end
end

class SpanSetMetricReturn
  def to_json(*_args)
    {}.to_json
  end
end

class SpanInjectArgs
  attr_accessor :span_id

  def initialize(params)
    @span_id = params['span_id']
  end
end

class SpanInjectReturn
  attr_accessor :http_headers

  def initialize(http_headers)
    @http_headers = http_headers
  end

  def to_json(*_args)
    { http_headers: @http_headers }.to_json
  end
end

class SpanExtractArgs
  attr_accessor :http_headers

  def initialize(params)
    @http_headers = params["http_headers"]
  end
end

class SpanExtractReturn
  attr_accessor :span_id

  def initialize(span_id)
    @span_id = span_id
  end

  def to_json(*_args)
    { span_id: @span_id }.to_json
  end
end

class TraceSpansFlushArgs
end

class TraceSpansFlushReturn
  def to_json(*_args)
    {}.to_json
  end
end

class TraceStatsFlushArgs
end

class TraceStatsFlushReturn
  def to_json(*_args)
    {}.to_json
  end
end

class TraceSpanErrorArgs
  attr_accessor :span_id, :type, :message, :stack

  def initialize(params)
    @span_id = params['span_id']
    @type = params['type']
    @message = params['message']
    @stack = params['stack']
  end
end

class TraceSpanErrorReturn
  def to_json(*_args)
    {}.to_json
  end
end

class TraceSpanAddLinksArgs
  attr_accessor :span_id, :parent_id, :attributes

  def initialize(params)
    @span_id = params['span_id']
    @parent_id = params['parent_id']
    @attributes = params['attributes']
  end

  def to_h
    { 'span_id' => @span_id, 'parent_id' => @parent_id, 'attributes' => @attributes }
  end
end

class TraceSpanAddLinkReturn
  def to_json(*_args)
    {}.to_json
  end
end

class HttpClientRequestArgs
  attr_accessor :method, :url, :headers, :body

  def initialize(params)
    @method = params['method']
    @url = params['url']
    @headers = params['headers']
    @body = params['body']
  end
end

class HttpClientRequestReturn
  def to_json(*_args)
    {}.to_json
  end
end

class OtelStartSpanArgs
  attr_accessor :name, :parent_id, :span_kind, :service, :resource, :type, :links, :timestamp,
                :attributes

  def initialize(params)
    @name = params['name']
    @parent_id = params['parent_id']
    @span_kind = params['span_kind']
    @service = params['service']
    @resource = params['resource']
    @type = params['type']
    @links = params['links']
    @timestamp = params['timestamp']
    @attributes = params['attributes']
  end
end

class OtelStartSpanReturn
  attr_accessor :span_id, :trace_id

  def initialize(span_id, trace_id)
    @span_id = span_id
    @trace_id = trace_id
  end

  def to_json(*_args)
    { span_id: @span_id, trace_id: @trace_id }.to_json
  end
end

class OtelAddEventArgs
  attr_accessor :span_id, :name, :timestamp, :attributes

  def initialize(params)
    @span_id = params['span_id']
    @name = params['name']
    @timestamp = params['timestamp']
    @attributes = params['attributes']
  end
end

class OtelAddEventReturn
  def to_json(*_args)
    {}.to_json
  end
end

class OtelRecordExceptionArgs
  attr_accessor :span_id, :message, :attributes

  def initialize(params)
    @span_id = params['span_id']
    @message = params['message']
    @attributes = params['attributes']
  end
end

class OtelRecordExceptionReturn
  def to_json(*_args)
    {}.to_json
  end
end

class OtelEndSpanArgs
  attr_accessor :id, :timestamp

  def initialize(params)
    @id = params['id']
    @timestamp = params['timestamp']
  end
end

class OtelEndSpanReturn
  def to_json(*_args)
    {}.to_json
  end
end

class OtelFlushSpansArgs
  attr_accessor :seconds

  def initialize(params)
    @seconds = params['seconds']
  end
end

class OtelFlushSpansReturn
  attr_accessor :success

  def initialize(success)
    @success = success
  end

  def to_json(*_args)
    { success: @success }.to_json
  end
end

class OtelIsRecordingArgs
  attr_accessor :span_id

  def initialize(params)
    @span_id = params['span_id']
  end
end

class OtelIsRecordingReturn
  attr_accessor :is_recording

  def initialize(is_recording)
    @is_recording = is_recording
  end

  def to_json(*_args)
    { is_recording: @is_recording }.to_json
  end
end

class OtelSpanContextArgs
  attr_accessor :span_id

  def initialize(params)
    @span_id = params['span_id']
  end
end

class OtelSpanContextReturn
  attr_accessor :span_id, :trace_id, :trace_flags, :trace_state, :remote

  def initialize(span_id, trace_id, trace_flags, trace_state, remote)
    @span_id = span_id
    @trace_id = trace_id
    @trace_flags = trace_flags
    @trace_state = trace_state
    @remote = remote
  end

  def to_json(*_args)
    {
      span_id: @span_id,
      trace_id: @trace_id,
      trace_flags: @trace_flags,
      trace_state: @trace_state,
      remote: @remote
    }.to_json
  end
end

class OtelSetStatusArgs
  attr_accessor :span_id, :code, :description

  def initialize(params)
    @span_id = params['span_id']
    @code = params['code']
    @description = params['description']
  end
end

class OtelSetStatusReturn
  def to_json(*_args)
    {}.to_json
  end
end

class OtelSetNameArgs
  attr_accessor :span_id, :name

  def initialize(params)
    @span_id = params['span_id']
    @name = params['name']
  end
end

class OtelSetNameReturn
  def to_json(*_args)
    {}.to_json
  end
end

class OtelSetAttributesArgs
  attr_accessor :span_id, :attributes

  def initialize(params)
    @span_id = params['span_id']
    @attributes = params['attributes']
  end
end

class OtelSetAttributesReturn
  def to_json(*_args)
    {}.to_json
  end
end

class TraceSpanAddEventsArgs
  attr_accessor :span_id, :name, :timestamp, :attributes

  def initialize(params)
    @span_id = params['span_id']
    @name = params['name']
    @timestamp = params['timestamp']
    @attributes = params['attributes']
  end
end

class TraceSpanAddEventReturn
  def to_json(*_args)
    {}.to_json
  end
end

def get_ddtrace_version
  Gem::Version.new(Datadog::VERSION)
end

def extract_http_headers(headers)
  headers = headers.group_by { |key, _| key }.transform_values do |values|
    values.map { |_, value| value }.join(', ')
  end
  if Datadog::Tracing::Contrib::HTTP.respond_to?(:extract)
    Datadog::Tracing::Contrib::HTTP.extract(headers)
  else
    Datadog::Tracing::Contrib::HTTP::Distributed::Propagation.new.extract(headers)
  end
end

# OTel system tests provide times in microseconds, but Ruby OTel
# measures time in seconds (Float).
def otel_correct_time(microseconds)
  unless microseconds.nil? || microseconds == 0
    microseconds / 1_000_000.0
  end
end

def get_digest(span_id)
  if span_id.nil?
    nil
  elsif DD_SPANS.key?(span_id)
    span = DD_SPANS[span_id]
    raise "Span id #{span_id} not found in span list: #{DD_SPANS}" if span.nil?
    trace = DD_TRACES[span.trace_id]
    raise "Span id #{span_id} not found in span list: #{DD_TRACES}" if trace.nil?
    trace.to_digest.merge(
      span_id: span.id,
      span_name: span.name,
      span_resource: span.resource,
      span_service: span.service,
      span_type: span.type,
      span_remote: false,
    )
  elsif DD_DIGEST.key?(span_id)
    DD_DIGEST[span_id]
  else
    raise "Span id #{span_id} not found in spans: #{DD_SPANS} or digests: #{DD_DIGEST}"
  end
end

def parse_otel_link(link)
  if OTEL_SPANS.key?(link['parent_id'])
    link_context = OTEL_SPANS[link['parent_id']].context
    OpenTelemetry::Trace::Link.new(
      link_context,
      link['attributes']
    )
  else
    raise "Parent id in #{link} not found in span list: #{OTEL_SPANS}"
  end
end

def digest_to_spancontext(digest)
  OpenTelemetry::Trace::SpanContext.new(
    trace_id: [format('%032x', digest.trace_id)].pack('H32'),
    span_id: [format('%016x', digest.span_id)].pack('H16'),
    trace_flags: OpenTelemetry::Trace::TraceFlags.from_byte(digest.trace_sampling_priority && digest.trace_sampling_priority > 0 ? 1 : 0),
    tracestate: OpenTelemetry::Trace::Tracestate.from_string(digest.trace_state),
    remote: digest.span_remote
  )
end

def find_span(span_id)
  span = Datadog::Tracing.active_span
  raise 'Request span is not the active span' unless span && span.id == span_id

  span
end

class MyApp
  def call(env)
    req = Rack::Request.new(env)
    res = Rack::Response.new

    case req.path_info
    when '/trace/span/start'
      handle_trace_span_start(req, res)
    when '/trace/span/finish'
      handle_trace_span_finish(req, res)
    when '/trace/span/set_meta'
      handle_trace_span_set_meta(req, res)
    when '/trace/config'
      handle_trace_config(req, res)
    when '/trace/span/set_metric'
      handle_trace_span_set_metric(req, res)
    when '/trace/span/inject_headers'
      handle_trace_span_inject_headers(req, res)
    when '/trace/span/extract_headers'
      handle_trace_span_extract_headers(req, res)
    when '/trace/span/flush'
      handle_trace_span_flush(req, res)
    when '/trace/stats/flush'
      handle_trace_stats_flush(req, res)
    when '/trace/span/error'
      handle_trace_span_error(req, res)
    when '/trace/span/add_link'
      handle_trace_span_add_link(req, res)
    when '/trace/span/add_event'
      handle_trace_span_add_event(req, res)
    when '/trace/otel/start_span'
      handle_trace_otel_start_span(req, res)
    when '/trace/otel/add_event'
      handle_trace_otel_add_event(req, res)
    when '/trace/otel/record_exception'
      handle_trace_otel_record_exception(req, res)
    when '/trace/otel/end_span'
      handle_trace_otel_end_span(req, res)
    when '/trace/otel/flush'
      handle_trace_otel_flush(req, res)
    when '/trace/otel/is_recording'
      handle_trace_otel_is_recording(req, res)
    when '/trace/otel/span_context'
      handle_trace_otel_span_context(req, res)
    when '/trace/otel/set_status'
      handle_trace_otel_set_status(req, res)
    when '/trace/otel/set_name'
      handle_trace_otel_set_name(req, res)
    when '/trace/otel/set_attributes'
      handle_trace_otel_set_attributes(req, res)
    when '/trace/crash'
      handle_trace_crash(req, res)
    else
      res.status = 404
      res.write('Not Found')
    end

    res.finish
  end

  def handle_trace_span_start(req, res)
    args = StartSpanArgs.new(JSON.parse(req.body.read))
    # If the parent span is the active span, we don't need to create a digest,
    # let the tracer handle span parenting. This avoids creating a new trace chunk.
    digest = unless Datadog::Tracing.active_span&.id == args.parent_id
      get_digest(args.parent_id)
    end

    span = Datadog::Tracing.trace(
      args.name,
      service: args.service,
      resource: args.resource,
      type: args.type,
      continue_from: digest,
      tags: args.span_tags.to_h
    )
    DD_SPANS[span.id] = span
    DD_TRACES[span.trace_id] = Datadog::Tracing.active_trace
    res.write(StartSpanReturn.new(span.id, span.trace_id).to_json)
  end

  def handle_trace_span_finish(req, res)
    args = SpanFinishArgs.new(JSON.parse(req.body.read))
    span = find_span(args.span_id)
    span.finish
    res.write(SpanFinishReturn.new.to_json)
  end

  def handle_trace_span_set_meta(req, res)
    args = SpanSetMetaArgs.new(JSON.parse(req.body.read))
    span = DD_SPANS[args.span_id]
    span.set_tag(args.key, args.value)
    res.write(SpanSetMetaReturn.new.to_json)
  end

  def handle_trace_config(_req, res)
    config = {}

    config["dd_service"] = Datadog.configuration.service || ""
    config["dd_trace_sample_rate"] = Datadog.configuration.tracing.sampling.default_rate.to_s
    config["dd_trace_enabled"] = Datadog.configuration.tracing.enabled.to_s
    config["dd_runtime_metrics_enabled"] = Datadog.configuration.runtime_metrics.enabled.to_s
    config["dd_trace_propagation_style"] = Datadog.configuration.tracing.propagation_style.join(",")
    config["dd_trace_debug"] = Datadog.configuration.diagnostics.debug.to_s
    config["dd_env"] = Datadog.configuration.env || ""
    config["dd_version"] = Datadog.configuration.version || ""
    config["dd_tags"] = Datadog.configuration.tags.nil? ? "" : Datadog.configuration.tags.map { |k, v| "#{k}:#{v}" }.join(",")
    config["dd_trace_rate_limit"] = Datadog.configuration.tracing.sampling.rate_limit.to_s
    config["dd_trace_agent_url"] = Datadog::Tracing::Diagnostics::EnvironmentCollector.collect_config![:agent_url] || ""
    config["dd_profiling_enabled"] = Datadog.configuration.profiling.enabled.to_s
    config["dd_logs_injection"] = Datadog.configuration.tracing.log_injection.to_s

    config["dd_data_streams_enabled"] = false.to_s # Not implemented

    res.write(TraceConfigReturn.new(config).to_json)
  end

  def handle_trace_span_set_metric(req, res)
    args = SpanSetMetricArgs.new(JSON.parse(req.body.read))
    span = find_span(args.span_id)
    span.set_metric(args.key, args.value)
    res.write(SpanSetMetricReturn.new.to_json)
  end

  def handle_trace_span_inject_headers(req, res)
    args = SpanInjectArgs.new(JSON.parse(req.body.read))
    digest = get_digest(args.span_id)
    env = {}
    if Datadog::Tracing::Contrib::HTTP.respond_to?(:inject)
      Datadog::Tracing::Contrib::HTTP.inject(digest, env)
    else
      Datadog::Tracing::Contrib::HTTP::Distributed::Propagation.new.inject!(digest, env)
    end

    res.write(SpanInjectReturn.new(env.to_a).to_json)
  end

  def handle_trace_span_extract_headers(req, res)
    args = SpanExtractArgs.new(JSON.parse(req.body.read))
    digest = extract_http_headers(args.http_headers)
    unless digest.nil?
      DD_DIGEST[digest.span_id] = digest
    end

    res.write(SpanExtractReturn.new(digest&.span_id).to_json)
  end

  def handle_trace_span_flush(_req, res)
    wait_for_flush(5)

    res.write(TraceSpansFlushReturn.new.to_json)
  end

  def handle_trace_stats_flush(_req, res)
    res.write(TraceStatsFlushReturn.new.to_json)
  end

  def handle_trace_span_error(req, res)
    args = TraceSpanErrorArgs.new(JSON.parse(req.body.read))
    span = find_span(args.span_id)
    span.set_error([
                     args.type,
                     args.message,
                     args.stack
                   ])
    res.write(TraceSpanErrorReturn.new.to_json)
  end

  def handle_trace_span_add_link(req, res)
    args = TraceSpanAddLinksArgs.new(JSON.parse(req.body.read))
    link = Datadog::Tracing::SpanLink.new(
      get_digest(args.parent_id),
      attributes: args.attributes
    )

    DD_SPANS[args.span_id].links.push(link)
    res.write(TraceSpanAddLinkReturn.new.to_json)
  end

  def handle_trace_span_add_event(req, res)
    args = TraceSpanAddEventsArgs.new(JSON.parse(req.body.read))
    span = find_span(args.span_id)
    
    # Create a new SpanEvent with the provided parameters
    event = Datadog::Tracing::SpanEvent.new(
      args.name,
      attributes: args.attributes,
      time_unix_nano: args.timestamp * 1000
    )
    
    # Add the event to the span's events array
    span.span_events << event
    
    res.write(TraceSpanAddEventReturn.new.to_json)
  end

  def handle_trace_crash(_req, res)
    STDOUT.puts "Crashing server..."
    Process.kill('SEGV', Process.pid)
    Process.wait2
  end

  def handle_trace_otel_start_span(req, res)
    js = JSON.parse(req.body.read)
    args = OtelStartSpanArgs.new(js)

    if args.parent_id
      parent_span = OTEL_SPANS[args.parent_id]
      parent_context = OpenTelemetry::Trace.context_with_span(parent_span)
    end
    if args.links
      otel_links = args.links.map do |link|
        parse_otel_link(link)
      end
    end
    span = otel_tracer.start_span(
      args.name,
      with_parent: parent_context,
      attributes: args.attributes,
      start_timestamp: otel_correct_time(args.timestamp),
      kind: OTEL_SPAN_KIND[args.span_kind],
      links: otel_links
    )
    # the otel trace id is oddly not 128-bit so we reach in and grab the
    # datadog spans trace id and convert it to 64-bit
    mask = (1 << 64) - 1
    t_id = span.datadog_span.trace_id & mask

    context = span.context

    span_id_b10 = context.hex_span_id.to_i(16)

    OTEL_SPANS[span_id_b10] = span
    res.write(OtelStartSpanReturn.new(span_id_b10, t_id).to_json)
  end

  def handle_trace_otel_add_event(req, res)
    args = OtelAddEventArgs.new(JSON.parse(req.body.read))
    span = OTEL_SPANS[args.span_id]
    span.add_event(
      args.name,
      timestamp: otel_correct_time(args.timestamp),
      attributes: args.attributes
    )
    res.write(OtelAddEventReturn.new.to_json)
  end

  def handle_trace_otel_record_exception(req, res)
    args = OtelRecordExceptionArgs.new(JSON.parse(req.body.read))

    span = OTEL_SPANS[args.span_id]
    span.record_exception(
      StandardError.new(args.message),
      attributes: args.attributes
    )
    res.write(OtelRecordExceptionReturn.new.to_json)
  end

  def handle_trace_otel_end_span(req, res)
    args = OtelEndSpanArgs.new(JSON.parse(req.body.read))

    span = OTEL_SPANS[args.id]
    span.finish(end_timestamp: otel_correct_time(args.timestamp))
    res.write(OtelEndSpanReturn.new.to_json)
  end

  def handle_trace_otel_flush(req, res)
    args = OtelFlushSpansArgs.new(JSON.parse(req.body.read))

    success = wait_for_flush(args.seconds)

    res.write(OtelFlushSpansReturn.new(success).to_json)
  end

  def handle_trace_otel_is_recording(req, res)
    args = OtelIsRecordingArgs.new(JSON.parse(req.body.read))

    span = OTEL_SPANS[args.span_id]
    res.write(OtelIsRecordingReturn.new(span.recording?).to_json)
  end

  def handle_trace_otel_span_context(req, res)
    args = OtelSpanContextArgs.new(JSON.parse(req.body.read))

    span = OTEL_SPANS[args.span_id]
    ctx = span.context

    res.write(OtelSpanContextReturn.new(
      format('%016x', ctx.hex_span_id.to_i(16)),
      format('%032x', ctx.hex_trace_id.to_i(16)),
      ctx.trace_flags.sampled? ? '01' : '00',
      ctx.tracestate.to_s,
      ctx.remote?
    ).to_json)
  end

  def handle_trace_otel_set_status(req, res)
    args = OtelSetStatusArgs.new(JSON.parse(req.body.read))

    span = OTEL_SPANS[args.span_id]
    span.status = OpenTelemetry::Trace::Status.public_send(
      args.code.downcase,
      args.description
    )

    res.write(OtelSetStatusReturn.new.to_json)
  end

  def handle_trace_otel_set_name(req, res)
    args = OtelSetNameArgs.new(JSON.parse(req.body.read))

    span = OTEL_SPANS[args.span_id]
    span.name = args.name

    res.write(OtelSetNameReturn.new.to_json)
  end

  def handle_trace_otel_set_attributes(req, res)
    args = OtelSetAttributesArgs.new(JSON.parse(req.body.read))

    span = OTEL_SPANS[args.span_id]
    args.attributes.each do |key, value|
      span.set_attribute(key, value)
    end

    res.write(OtelSetAttributesReturn.new.to_json)
  end

  def get_ddtrace_version
    Gem::Version.new(DDTrace::VERSION)
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
end

# Run the Rack app
Rack::Handler::WEBrick.run MyApp.new, Host: '0.0.0.0', Port: ENV.fetch('APM_TEST_CLIENT_SERVER_PORT')
