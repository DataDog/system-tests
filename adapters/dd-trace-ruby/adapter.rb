# dd-trace-rb implementation of the Temper-generated Tracer interface.
#
# Mirrors the dd-trace-py adapter: implements the conformance `Tracer` surface
# against a real `datadog` (dd-trace-rb) tracer. Span/trace ids are decimal
# strings (trace id is the low 64 bits, matching the agent payload). Spans are
# read back from the ddapm-test-agent (`captured_spans`/`delivered_spans`), so
# the capture reflects the real on-the-wire serialization.
#
# The rust cdylib (see CONTRACT.md) calls `Dispatch.handle(op, args)` once per
# Tracer method; `op` is the snake_case method name and `args` is the decoded
# JSON args array. `handle` returns a plain Ruby value that run_one.rb encodes
# to the CONTRACT JSON. Unimplemented ops return {"__unsupported__" => true} so
# the case SKIPs (matching the other adapters).

require "datadog"
require "json"
require "net/http"
require "uri"

# Register components (incl. the HTTP distributed propagator) from the process
# env. The case env is applied before this file loads (run.rb subprocess env),
# so configuration here reflects the case's DD_* vars.
Datadog.configure {}

module Dispatch
  MASK64 = (1 << 64) - 1
  TD = Datadog::Tracing::TraceDigest
  HTTP = Datadog::Tracing::Contrib::HTTP

  @by_id = {}        # decimal span id -> Datadog::Tracing::SpanOperation
  @trace_by_id = {}  # decimal span id -> Datadog::Tracing::TraceOperation
  @ctx_by_id = {}    # parent id (or "bgctx<n>") -> extracted TraceDigest
  @order = []        # span ids in creation order
  @ctx_counter = 0

  class << self
    def handle(op, args)
      case op
      when "start_span"       then start_span(*args)
      when "finish_span"      then finish_span(*args)
      when "set_meta"         then set_meta(*args)
      when "set_metric"       then set_metric(*args)
      when "set_resource"     then set_resource(*args)
      when "remove_meta"      then remove_meta(*args)
      when "remove_metric"    then remove_metric(*args)
      when "add_link"         then add_link(*args)
      when "set_baggage"      then set_baggage(*args)
      when "get_baggage"      then get_baggage(*args)
      when "get_all_baggage"  then get_all_baggage(*args)
      when "remove_baggage"   then remove_baggage(*args)
      when "remove_all_baggage" then remove_all_baggage(*args)
      when "extract_headers"  then extract_headers(*args)
      when "inject_headers"   then inject_headers(*args)
      when "flush"            then flush
      when "captured_spans"   then captured_spans
      when "delivered_spans"  then captured_spans
      when "config"           then config
      else
        { "__unsupported__" => true }
      end
    rescue => e
      # An op that blows up is treated as unsupported so the case SKIPs rather
      # than aborting the whole process; run_one.rb surfaces the reason.
      { "__unsupported__" => true, "error" => "#{e.class}: #{e.message}" }
    end

    # --- span lifecycle ---------------------------------------------------

    def start_span(name, parent_id, service = "", resource = "", span_type = "")
      # Reset the active-trace context so each span nests exactly where the
      # conformance model says (dd-trace-rb otherwise auto-nests under whatever
      # span is currently active).
      Datadog::Tracing.continue_trace!(nil)
      kwargs = {}
      kwargs[:service]  = service   unless blank?(service)
      kwargs[:resource] = resource  unless blank?(resource)
      kwargs[:type]     = span_type unless blank?(span_type)
      parent = parent_context(parent_id)
      kwargs[:continue_from] = parent if parent

      span  = Datadog::Tracing.trace(name, **kwargs)
      trace = Datadog::Tracing.active_trace
      sid = span.id.to_s
      @by_id[sid] = span
      @trace_by_id[sid] = trace
      @order << sid

      captured_span_stub(span, parent_id, name, service, resource, span_type)
    end

    def finish_span(span_id)
      @by_id[span_id]&.finish
      nil
    end

    def set_meta(span_id, key, value)
      @by_id[span_id]&.set_tag(key, value)
      nil
    end

    def set_metric(span_id, key, value)
      @by_id[span_id]&.set_metric(key, value)
      nil
    end

    def set_resource(span_id, value)
      s = @by_id[span_id]
      s.resource = value if s
      nil
    end

    def remove_meta(span_id, key)
      @by_id[span_id]&.clear_tag(key)
      nil
    end

    def remove_metric(span_id, key)
      @by_id[span_id]&.clear_metric(key)
      nil
    end

    def add_link(span_id, link_to_span_id, attributes)
      span = @by_id[span_id]
      return nil unless span

      digest = link_target_digest(link_to_span_id)
      return nil unless digest

      attrs = (attributes || {}).transform_values(&:to_s)
      span.links << Datadog::Tracing::SpanLink.new(digest, attributes: attrs)
      nil
    end

    # --- baggage ----------------------------------------------------------

    def set_baggage(span_id, key, value)
      trace = @trace_by_id[span_id]
      return nil unless trace

      bag = (trace.baggage || {}).dup
      bag[key] = value
      trace.baggage = bag
      nil
    end

    def get_baggage(span_id, key)
      trace = @trace_by_id[span_id]
      return "" unless trace

      (trace.baggage || {})[key].to_s
    end

    def get_all_baggage(span_id)
      trace = @trace_by_id[span_id]
      return {} unless trace

      (trace.baggage || {}).each_with_object({}) { |(k, v), h| h[k.to_s] = v.to_s }
    end

    def remove_baggage(span_id, key)
      trace = @trace_by_id[span_id]
      return nil unless trace

      bag = (trace.baggage || {}).dup
      bag.delete(key)
      trace.baggage = bag
      nil
    end

    def remove_all_baggage(span_id)
      trace = @trace_by_id[span_id]
      trace.baggage = {} if trace
      nil
    end

    # --- distributed headers ---------------------------------------------

    def extract_headers(headers)
      # Fold repeated headers with commas (RFC 7230) so duplicate
      # traceparent/tracestate/baggage inputs are represented faithfully in the
      # single-value carrier hash the propagator expects.
      # HTTP headers are case-insensitive; dd-trace-rb reads lowercase keys, so
      # normalize (the suite sends mixed-case in the *_valid_casing cases).
      carrier = {}
      (headers || []).each do |pair|
        k, v = pair
        k = k.downcase
        carrier[k] = carrier.key?(k) ? "#{carrier[k]},#{v}" : v
      end
      digest = HTTP.extract(carrier)
      return "0" if digest.nil?

      if digest.span_id && digest.span_id != 0
        pid = digest.span_id.to_s
        @ctx_by_id[pid] = digest
        return pid
      end
      # trace-less context that still carries baggage: keep it so a child span
      # started from it inherits the baggage (baggage-only propagation).
      if digest.baggage && !digest.baggage.empty?
        @ctx_counter += 1
        pid = "bgctx#{@ctx_counter}"
        @ctx_by_id[pid] = digest
        return pid
      end
      "0"
    end

    def inject_headers(span_id)
      span = @by_id[span_id]
      return {} unless span

      digest = span_digest(span_id)
      return {} unless digest

      carrier = {}
      HTTP.inject(digest, carrier)
      carrier.each_with_object({}) { |(k, v), h| h[k.to_s] = v.to_s }
    end

    # --- flush + capture --------------------------------------------------

    def flush
      # shutdown! synchronously flushes all buffered traces to the agent (the
      # writer's async worker only flushes on its own interval otherwise). A
      # conformance case calls flush before reading spans back, so a synchronous
      # flush is what we want; the per-case subprocess exits right after.
      Datadog::Tracing.shutdown!
      nil
    end

    def captured_spans
      return [] unless Datadog::Tracing.enabled?

      flush
      spans_from_agent
    end

    # --- resolved config --------------------------------------------------

    def config
      c = Datadog.configuration
      t = c.tracing
      {
        "dd_service"                => str_or_null(c.service),
        "dd_env"                    => str_or_null(c.env),
        "dd_version"                => str_or_null(c.version),
        "dd_trace_agent_url"        => str_or_null(agent_url),
        "dd_trace_sample_rate"      => str_or_null(t.sampling.default_rate),
        "dd_trace_rate_limit"       => str_or_null(t.sampling.rate_limit),
        "dd_trace_enabled"          => bool_low(t.enabled),
        "dd_trace_debug"            => bool_low(c.diagnostics.debug),
        "dd_runtime_metrics_enabled" => bool_low(c.runtime_metrics.enabled),
        "dd_trace_otel_enabled"     => bool_low(otel_enabled?(c)),
        "dd_trace_propagation_style" => propagation_style(t),
        "dd_tags"                   => tags_csv(c.tags),
      }
    end

    # --- helpers ----------------------------------------------------------

    private

    def blank?(s)
      s.nil? || s == ""
    end

    def parent_context(parent_id)
      return nil if blank?(parent_id) || parent_id == "0"

      # Prefer a context extracted from headers (carries sampling/baggage/tags).
      return @ctx_by_id[parent_id] if @ctx_by_id.key?(parent_id)

      span_digest(parent_id)
    end

    # A TraceDigest that positions a child under the given local span within its
    # trace (preserving trace-level sampling/origin/tags/baggage).
    def span_digest(span_id)
      span  = @by_id[span_id]
      trace = @trace_by_id[span_id]
      return nil unless span && trace

      d = trace.to_digest
      TD.new(
        trace_id: d.trace_id,
        span_id: span.id,
        trace_sampling_priority: d.trace_sampling_priority,
        trace_origin: d.trace_origin,
        trace_distributed_tags: d.trace_distributed_tags,
        trace_flags: d.trace_flags,
        trace_state: d.trace_state,
        baggage: d.baggage,
      )
    end

    def link_target_digest(link_to_span_id)
      return @ctx_by_id[link_to_span_id] if @ctx_by_id.key?(link_to_span_id)

      span = @by_id[link_to_span_id]
      return nil unless span

      TD.new(trace_id: span.trace_id, span_id: span.id)
    end

    def captured_span_stub(span, parent_id, name, service, resource, span_type)
      {
        "trace_id"  => (span.trace_id & MASK64).to_s,
        "span_id"   => span.id.to_s,
        "parent_id" => (blank?(parent_id) ? "0" : parent_id),
        "name"      => name,
        "service"   => service.to_s,
        "resource"  => resource.to_s,
        "span_type" => span_type.to_s,
        "meta"      => {},
        "metrics"   => {},
        "links"     => [],
        "error"     => nil,
      }
    end

    def agent_base
      ENV["DD_TRACE_AGENT_URL"].to_s.sub(%r{/\z}, "")
    end

    def agent_get(path)
      base = agent_base
      return nil if base.empty?

      uri = URI.parse(base + path)
      Net::HTTP.start(uri.host, uri.port, open_timeout: 3, read_timeout: 3) do |http|
        res = http.get(uri.request_uri)
        res.is_a?(Net::HTTPSuccess) ? res.body : nil
      end
    rescue StandardError
      nil
    end

    def spans_from_agent
      deadline = Time.now + 8
      while Time.now < deadline
        raw = agent_get("/test/session/traces")
        traces = raw ? (JSON.parse(raw) rescue []) : []
        unless traces.empty?
          out = []
          traces.each do |trace|
            trace.each { |sp| out << agent_span_to_captured(sp) }
          end
          return out
        end
        sleep 0.3
      end
      []
    end

    def agent_span_to_captured(sp)
      meta = (sp["meta"] || {}).each_with_object({}) { |(k, v), h| h[k.to_s] = v.to_s }
      metrics = {}
      (sp["metrics"] || {}).each do |k, v|
        metrics[k.to_s] = v.to_f if v.is_a?(Numeric)
      end
      links = (sp["span_links"] || []).map do |l|
        {
          "span_id"       => (l["span_id"] || 0).to_s,
          "trace_id"      => (l["trace_id"] || 0).to_s,
          "trace_id_high" => (l["trace_id_high"] || 0).to_s,
          "attributes"    => (l["attributes"] || {}).each_with_object({}) { |(k, v), h| h[k.to_s] = v.to_s },
        }
      end
      {
        "trace_id"  => sp["trace_id"].to_s,
        "span_id"   => sp["span_id"].to_s,
        "parent_id" => (sp["parent_id"] || 0).to_s,
        "name"      => (sp["name"] || "").to_s,
        "service"   => (sp["service"] || "").to_s,
        "resource"  => (sp["resource"] || "").to_s,
        "span_type" => (sp["type"] || "").to_s,
        "meta"      => meta,
        "metrics"   => metrics,
        "links"     => links,
        "error"     => (sp["error"] || 0).to_i,
      }
    end

    def agent_url
      Datadog.send(:components).agent_settings.url
    rescue StandardError
      ENV["DD_TRACE_AGENT_URL"]
    end

    def otel_enabled?(c)
      c.tracing.instrument?(:opentelemetry) rescue false
    rescue StandardError
      false
    end

    def propagation_style(t)
      styles = t.propagation_style_inject
      styles && !styles.empty? ? styles.join(",") : "null"
    end

    def tags_csv(tags)
      return "null" if tags.nil? || tags.empty?

      tags.map { |k, v| "#{k}:#{v}" }.join(",")
    end

    def str_or_null(v)
      v.nil? ? "null" : v.to_s
    end

    def bool_low(v)
      v ? "true" : "false"
    end
  end
end
