require 'sinatra'
require 'json'
require 'ddtrace'
require 'opentelemetry/sdk'
require 'opentelemetry/exporter/otlp'
require 'opentelemetry/instrumentation/all'
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
  if ENV['DD_TRACE_DEBUG'].nil?
    # If DD_TRACE_DEBUG is set do not override this configuration.
    c.diagnostics.debug = true # When tests fail, ensure there's enough data to debug the failure.
  end
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

set :port, 4567

dd_spans = {}
otel_spans = {}
dd_traces = {}

class StartSpanArgs
  attr_accessor :parent_id, :name, :service, :type, :resource, :origin, :http_headers, :links

  def initialize(params)
    @parent_id = params['parent_id']
    @name = params['name']
    @service = params['service']
    @type = params['type']
    @resource = params['resource']
    @origin = params['origin']
    @http_headers = params['http_headers']
    @links = params['links']
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
  attr_accessor :name, :parent_id, :span_kind, :service, :resource, :type, :links, :timestamp, :http_headers, :attributes

  def initialize(params)
    @name = params['name']
    @parent_id = params['parent_id']
    @span_kind = params['span_kind']
    @service = params['service']
    @resource = params['resource']
    @type = params['type']
    @links = params['links']
    @timestamp = params['timestamp']
    @http_headers = params['http_headers']
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

def get_ddtrace_version
  Gem::Version.new(Datadog::VERSION)
end

def extract_http_headers(headers)
  if Datadog::Tracing::Contrib::HTTP.respond_to?(:extract)
    Datadog::Tracing::Contrib::HTTP.extract(headers.to_h)
  else
    Datadog::Tracing::Contrib::HTTP::Distributed::Propagation.new.extract(headers.to_h)
  end
end



def parse_dd_link(link)
  link_dg = if link.http_headers != nil && link.http_headers.http_headers.size != nil
              headers = link.http_headers.http_headers.group_by(&:key).map do |name, values|
                          [name, values.map(&:value).join(', ')]
                        end
              extract_http_headers(headers)
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
    attributes: link['attributes']
  )
end

def find_span(span_id)
  span = Datadog::Tracing.active_span
  raise 'Request span is not the active span' unless span && span.id == span_id

  span
end

post '/trace/span/start' do
  args = StartSpanArgs.new(JSON.parse(request.body.read))

  digest = if args.http_headers.http_headers.size != 0
    # Emulate how Rack headers concatenates header with duplicate values with a `, `.
    headers = args.http_headers.http_headers.group_by(&:key).map do |name, values|
      [name, values.map(&:value).join(', ')]
    end
    extract_http_headers(headers)
  elsif !args.origin.empty? || args.parent_id != 0
    # DEV: Parametric tests do not differentiate between a distributed span request from a span parenting request.
    # DEV: We have to consider the parent_id being present present and origin being absent as a span parenting request.
    # DEV: This is incorrect because a distributed request can have an absent origin.
    if !args.origin.empty?
      Datadog::Tracing::TraceDigest.new(trace_origin: args.origin, span_id: args.parent_id)
    else
      unless Datadog::Tracing.active_span&.id == args.parent_id
        raise "active parent span id (#{Datadog::Tracing.active_span&.id}) does not match requested parent_id (#{args.parent_id})"
      end
    end
  end

  span = Datadog::Tracing.trace(
    args.name,
    service: args.service,
    resource: args.resource,
    type: args.type,
    continue_from: digest,
  )

  span.links = args.links do |link|
    parse_dd_link(link)
  end if args.span_links.size > 0

  dd_spans[span.id] = span
  dd_traces[span.trace_id] = Datadog::Tracing.active_trace

  StartSpanReturn.new(span.span_id, span.trace_id).to_json

end


post '/trace/span/finish' do
  args = SpanFinishArgs.new(JSON.parse(request.body.read))
  span = spans[args.span_id]
  span.finish
  SpanFinishReturn.new.to_json
end

get '/trace/config' do
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
  TraceConfigReturn.new(config).to_json
end

post '/trace/span/set_meta' do
  args = SpanSetMetaArgs.new(JSON.parse(request.body.read))
  span = spans[args.span_id]
  span.set_tag(args.key, args.value)
  SpanSetMetaReturn.new.to_json
end


post '/trace/span/set_metric' do
  args = SpanSetMetricArgs.new(JSON.parse(request.body.read))
  span = find_span(args.span_id)
  span.set_metric(args.key, args.value)
  SpanSetMetricReturn.new.to_json
end

post '/trace/span/inject_headers' do
  args = SpanInjectArgs.new(JSON.parse(request.body.read))
  find_span(args.span_id)
  env = {}
    if Datadog::Tracing::Contrib::HTTP.respond_to?(:inject)
      Datadog::Tracing::Contrib::HTTP.inject(Datadog::Tracing.active_trace.to_digest, env)
    else
      Datadog::Tracing::Contrib::HTTP::Distributed::Propagation.new.inject!(Datadog::Tracing.active_trace.to_digest, env)
    end

    tuples = env.map do |key, value|
      HeaderTuple.new(key:, value:)
    end
  SpanInjectReturn.new(http_headers: DistributedHTTPHeaders.new(http_headers: tuples))
end

post '/trace/span/flush' do
  wait_for_flush(5)

  TraceSpansFlushReturn.new.to_json
end

post '/trace/stats/flush' do
  TraceStatsFlushReturn.new.to_json
end

post '/trace/span/error' do
  args = TraceSpanErrorArgs.new(JSON.parse(request.body.read))
  span = find_span(args.span_id)
  span.set_error([
                     args.type,
                     args.message,
                     args.stack,
                   ])
  TraceSpanErrorReturn.new.to_json
end

post '/trace/span/add_link' do
  args = TraceSpanAddLinksArgs.new(JSON.parse(request.body.read))
  link = parse_dd_link(args.span_link)
  dd_spans[args.span_id].links.push(link)
  TraceSpanAddLinkReturn.new.to_json
end

post '/http/client/request' do
  url = URI(args.url)
  headers = args.headers.http_headers.map{|x|[x.key, x.value] }.to_h
  method = args.to_h[:method]

  request_class = Net::HTTP.const_get(method.capitalize)
  request = request_class.new(url, headers).tap { |r| r.body = args.body }

  Net::HTTP.start(url.hostname, url.port, use_ssl: url.scheme == 'https') do |http|
    http.request(request)
  end
  HttpClientRequestReturn.new.to_json
end


post '/trace/otel/start_span' do
  content_type :json
  args = OtelStartSpanArgs.new(JSON.parse(request.body.read, symbolize_names: true))
  
  otel_tracer = OpenTelemetry.tracer_provider.tracer(__FILE__)
  
  parent_span = if args.parent_id
                  otel_spans[args.parent_id]
                elsif args.http_headers
                  headers = args.http_headers.to_h
                  ddcontext = HTTPPropagator.extract(headers)
                  OtelNonRecordingSpan.new(
                    OtelSpanContext.new(
                      ddcontext.trace_id,
                      ddcontext.span_id,
                      true,
                      ddcontext.sampling_priority && ddcontext.sampling_priority > 0 ? TraceFlags::SAMPLED : TraceFlags::DEFAULT,
                      TraceState.from_header([ddcontext._tracestate])
                    )
                  )
                end
  
  links = args.links.map do |link|
    parent_id = link[:parent_id] || 0
    span_context = if parent_id > 0
                     otel_spans[parent_id].span_context
                   else
                     headers = link[:http_headers].to_h
                     ddcontext = HTTPPropagator.extract(headers)
                     OtelSpanContext.new(
                       ddcontext.trace_id,
                       ddcontext.span_id,
                       true,
                       ddcontext.sampling_priority && ddcontext.sampling_priority > 0 ? TraceFlags::SAMPLED : TraceFlags::DEFAULT,
                       TraceState.from_header([ddcontext._tracestate])
                     )
                   end
    OpenTelemetry::Trace::Link.new(span_context, link[:attributes])
  end
  
  otel_span = otel_tracer.start_span(
    args.name,
    with_parent: parent_span,
    kind: args.span_kind,
    attributes: args.attributes,
    links: links,
    start_timestamp: args.timestamp ? args.timestamp * 1e3 : nil,
    record_exception: true,
    set_status_on_exception: true
  )
  
  ctx = otel_span.context
  otel_spans[ctx.span_id] = otel_span
  OtelStartSpanReturn.new(ctx.span_id, ctx.trace_id).to_json
end

post '/trace/otel/add_event' do
  content_type :json
  args = OtelAddEventArgs.new(JSON.parse(request.body.read, symbolize_names: true))
  
  span = otel_spans[args.span_id]
  span.add_event(args.name, attributes: args.attributes, timestamp: args.timestamp)
  
  OtelAddEventReturn.new.to_json
end


class OtelRecordExceptionArgs
  attr_accessor :span_id, :message, :attributes
  
  def initialize(params)
    @span_id = params[:span_id]
    @message = params[:message]
    @attributes = params[:attributes]
  end
end

class OtelRecordExceptionReturn
  def to_json(*_args)
    {}.to_json
  end
end

post '/trace/otel/record_exception' do
  content_type :json
  args = OtelRecordExceptionArgs.new(JSON.parse(request.body.read, symbolize_names: true))
  
  span = otel_spans[args.span_id]
  span.record_exception(Exception.new(args.message), attributes: args.attributes)
  
  OtelRecordExceptionReturn.new.to_json
end

class OtelEndSpanArgs
  attr_accessor :id, :timestamp
  
  def initialize(params)
    @id = params[:id]
    @timestamp = params[:timestamp]
  end
end

class OtelEndSpanReturn
  def to_json(*_args)
    {}.to_json
  end
end

post '/trace/otel/end_span' do
  content_type :json
  args = OtelEndSpanArgs.new(JSON.parse(request.body.read, symbolize_names: true))
  
  span = otel_spans[args.id]
  st = args.timestamp ? args.timestamp * 1e3 : nil
  span.finish(end_timestamp: st)
  
  OtelEndSpanReturn.new.to_json
end

class OtelFlushSpansArgs
  attr_accessor :seconds
  
  def initialize(params)
    @seconds = params[:seconds] || 1
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

post '/trace/otel/flush' do
  content_type :json
  args = OtelFlushSpansArgs.new(JSON.parse(request.body.read, symbolize_names: true))
  
  ddtrace.tracer.writer.flush
  spans.clear
  otel_spans.clear
  
  OtelFlushSpansReturn.new(true).to_json
end

class OtelIsRecordingArgs
  attr_accessor :span_id
  
  def initialize(params)
    @span_id = params[:span_id]
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

post '/trace/otel/is_recording' do
  content_type :json
  args = OtelIsRecordingArgs.new(JSON.parse(request.body.read, symbolize_names: true))
  
  span = otel_spans[args.span_id]
  OtelIsRecordingReturn.new(span.recording?).to_json
end

class OtelSpanContextArgs
  attr_accessor :span_id
  
  def initialize(params)
    @span_id = params[:span_id]
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

post '/trace/otel/span_context' do
  content_type :json
  args = OtelSpanContextArgs.new(JSON.parse(request.body.read, symbolize_names: true))
  
  span = otel_spans[args.span_id]
  ctx = span.context
  
  OtelSpanContextReturn.new(
    format('%016x', ctx.span_id),
    format('%032x', ctx.trace_id),
    format('%02x', ctx.trace_flags),
    ctx.trace_state.to_s,
    ctx.remote?
  ).to_json
end

class OtelSetStatusArgs
  attr_accessor :span_id, :code, :description
  
  def initialize(params)
    @span_id = params[:span_id]
    @code = params[:code]
    @description = params[:description]
  end
end

class OtelSetStatusReturn
  def to_json(*_args)
    {}.to_json
  end
end

post '/trace/otel/set_status' do
  content_type :json
  args = OtelSetStatusArgs.new(JSON.parse(request.body.read, symbolize_names: true))
  
  span = otel_spans[args.span_id]
  status_code = OpenTelemetry::Trace::Status::StatusCode.const_get(args.code.upcase)
  span.status = OpenTelemetry::Trace::Status.new(status_code, description: args.description)
  
  OtelSetStatusReturn.new.to_json
end

class OtelSetNameArgs
  attr_accessor :span_id, :name
  
  def initialize(params)
    @span_id = params[:span_id]
    @name = params[:name]
  end
end

class OtelSetNameReturn
  def to_json(*_args)
    {}.to_json
  end
end

post '/trace/otel/set_name' do
  content_type :json
  args = OtelSetNameArgs.new(JSON.parse(request.body.read, symbolize_names: true))
  
  span = otel_spans[args.span_id]
  span.name = args.name
  
  OtelSetNameReturn.new.to_json
end

class OtelSetAttributesArgs
  attr_accessor :span_id, :attributes
  
  def initialize(params)
    @span_id = params[:span_id]
    @attributes = params[:attributes]
  end
end

class OtelSetAttributesReturn
  def to_json(*_args)
    {}.to_json
  end
end

post '/trace/otel/set_attributes' do
  content_type :json
  args = OtelSetAttributesArgs.new(JSON.parse(request.body.read, symbolize_names: true))
  
  span = otel_spans[args.span_id]
  span.set_attributes(args.attributes)
  
  OtelSetAttributesReturn.new.to_json
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