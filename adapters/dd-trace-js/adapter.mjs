// dd-trace-js implementation of the Temper-generated Tracer interface.
// Exported as a factory so the per-case runner can build it after the tracer
// has been initialized with that case's env.
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const require = createRequire(import.meta.url)
const { execSync } = require('node:child_process')
const here = path.dirname(fileURLToPath(import.meta.url))
export const repoRoot = path.resolve(here, '..', '..')

export const lib = await import(
  path.join(repoRoot, 'temper.out/js/system-tests-redux/system_tests_redux.js')
)

const { Tracer, CapturedSpan, CapturedLink, OtelSpanContextInfo, TelemetryConfigItem } = lib

// Capture the app-started telemetry configuration by wrapping the telemetry
// send (must be patched before the tracer initializes).
let capturedTelemetry = null
try {
  const sd = require('dd-trace/packages/dd-trace/src/telemetry/send-data')
  const origSend = sd.sendData
  sd.sendData = function (c, a, h, reqType, payload, cb) {
    if (reqType === 'app-started' && payload && payload.configuration) capturedTelemetry = payload.configuration
    return origSend.apply(this, arguments)
  }
} catch {}
const dec = (idObj) => (idObj == null ? '0' : idObj.toString(10))
const hexToDec = (hex) => BigInt('0x' + hex).toString()

export function makeAdapter (tracer, otel = otelApi) {
  const otelApi = otel
  let otelTracer = null
  if (otelApi) {
    try {
      const { TracerProvider } = tracer
      new TracerProvider().register()
      otelTracer = otelApi.trace.getTracer('conformance')
    } catch {}
  }
  // Capture the *formatted* (agent-wire) spans the processor produces, so we
  // see serialization-time data (single-span sampling tags, rule_psr, origin,
  // _dd.p.tid, final meta/metrics). Links aren't in the formatted shape, so we
  // read those from the live span objects (keyed by decimal span id).
  const formatted = []
  const exporter = tracer._tracer?._exporter
  if (exporter && typeof exporter.export === 'function') {
    exporter.export = (spans) => { for (const s of spans) formatted.push(s) }
  }
  const dec10 = (idObj) => (idObj == null ? '0' : idObj.toString(10))
  const encoder = tracer._tracer?._exporter?._writer?._encoder
  const v05encoder = V05Encoder ? new V05Encoder(8 << 20, 8 << 20) : null

  class DdTraceAdapter extends Tracer {
    #byId = new Map()
    #ctxById = new Map()
    #order = []
    #formatted = formatted

    #parentFor (parentId) {
      if (parentId === '0' || !parentId) return undefined
      return this.#byId.get(parentId) ?? this.#ctxById.get(parentId)
    }

    startSpan (name, parentId, service = '', resource = '', spanType = '') {
      const childOf = this.#parentFor(parentId)
      const tags = {}
      // sampler matches on the `service` tag; `service.name` is derived from it
      if (service) tags.service = service
      if (resource) tags['resource.name'] = resource
      if (spanType) tags['span.type'] = spanType
      const span = tracer.startSpan(name, { ...(childOf ? { childOf } : {}), tags })
      const sid = span.context().toSpanId()
      this.#byId.set(sid, span)
      this.#order.push(span)
      return new CapturedSpan(
        span.context().toTraceId(), sid, parentId, name,
        service, resource, spanType, new Map(), new Map(), [],
      )
    }

    finishSpan (spanId) { this.#byId.get(spanId)?.finish() }
    setMeta (spanId, key, value) { this.#byId.get(spanId)?.setTag(key, value) }
    setMetric (spanId, key, value) { this.#byId.get(spanId)?.setTag(key, value) }
    setResource (spanId, value) { this.#byId.get(spanId)?.setTag('resource.name', value) }
    removeMeta (spanId, key) { this.#byId.get(spanId)?.setTag(key, undefined) }
    removeMetric (spanId, key) { this.#byId.get(spanId)?.setTag(key, undefined) }
    otelSetAttributeNum (spanId, key, value) { this.#otelById.get(spanId)?.setAttribute(key, value) }
    otelRemoveAttribute (spanId, key) { this.#otelById.get(spanId)?.setAttribute(key, undefined) }
    deliveredSpans () {
      // dd-trace-js delivery is decided at the processor->exporter handoff, which
      // our export hook already captures (incl. partial-flush chunks). Node's
      // single event loop can't be driven synchronously, so we read those rather
      // than round-trip a (blocked) async send to the agent.
      return this.capturedSpans()
    }
    rcCapabilitiesCsv () {
      const base = (process.env.DD_TRACE_AGENT_URL || '').replace(/\/$/, '')
      if (!base) return ''
      // A synchronous run function can't drive node's event loop, so let a
      // short-lived dd-trace process poll RC against the agent (capability
      // advertisement is a property of the library build, not the instance).
      try { execSync(`${process.execPath} ${path.join(here, 'rc-poll.mjs')}`, { stdio: 'ignore', timeout: 9000 }) } catch {}
      try {
        const reqs = JSON.parse(execSync(`curl -s ${base}/test/session/requests`, { encoding: 'utf8', timeout: 4000 }) || '[]')
        for (const r of reqs) {
          if (!String(r.url).includes('/v0.7/config')) continue
          let body = r.body
          if (typeof body === 'string') body = JSON.parse(Buffer.from(body, 'base64').toString())
          const caps = body?.client?.capabilities
          if (!caps) continue
          const raw = typeof caps === 'string' ? Buffer.from(caps, 'base64') : Buffer.from(caps)
          let n = 0n
          for (const byte of raw) n = (n << 8n) | BigInt(byte)
          const bits = []
          for (let i = 0; i < 64; i++) if (n & (1n << BigInt(i))) bits.push(String(i))
          if (bits.length) return ',' + bits.join(',') + ','
        }
      } catch {}
      return ''
    }
    rcApplySamplingRate (rate) { return false }
    computedStatsJson () {
      this.flush()
      const base = (process.env.DD_TRACE_AGENT_URL || '').replace(/\/$/, '')
      if (!base) return ''
      const deadline = Date.now() + 14000
      while (Date.now() < deadline) {
        let stats = []
        try { stats = JSON.parse(execSync(`curl -s ${base}/test/session/stats`, { encoding: 'utf8', timeout: 4000 }) || '[]') } catch {}
        if (stats.length) return JSON.stringify(stats)
        Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 500)
      }
      return ''
    }

    setBaggage (spanId, key, value) { this.#byId.get(spanId)?.setBaggageItem(key, value) }
    getBaggage (spanId, key) { return this.#byId.get(spanId)?.getBaggageItem(key) ?? '' }
    getAllBaggage (spanId) {
      const out = new Map()
      const span = this.#byId.get(spanId)
      if (span) {
        const all = JSON.parse(span.getAllBaggageItems() || '{}')
        for (const k of Object.keys(all)) out.set(k, String(all[k]))
      }
      return out
    }
    removeBaggage (spanId, key) { this.#byId.get(spanId)?.removeBaggageItem(key) }
    removeAllBaggage (spanId) { this.#byId.get(spanId)?.removeAllBaggageItems() }

    addLink (spanId, linkToSpanId, attributes) {
      const span = this.#byId.get(spanId)
      const target = this.#byId.get(linkToSpanId)
      const ctx = target ? target.context() : this.#ctxById.get(linkToSpanId)
      const attrs = {}
      for (const [k, v] of attributes) attrs[k] = v
      span.addLink({ context: ctx, attributes: attrs })
    }

    extractHeaders (headers) {
      const carrier = {}
      // fold repeated headers with commas (RFC 7230), so duplicate
      // traceparent/tracestate inputs are represented faithfully
      for (const p of headers) {
        const k = String(p.key).toLowerCase()
        carrier[k] = (k in carrier) ? `${carrier[k]},${p.value}` : p.value
      }
      const ctx = tracer.extract('http_headers', carrier)
      if (ctx && ctx._spanId) {
        const pid = ctx.toSpanId()
        this.#ctxById.set(pid, ctx)
        return pid
      }
      return '0'
    }

    injectHeaders (spanId) {
      const span = this.#byId.get(spanId)
      const carrier = {}
      tracer.inject(span, 'http_headers', carrier)
      const out = new Map()
      for (const k of Object.keys(carrier)) out.set(k, String(carrier[k]))
      return out
    }

    flush () {
      try { tracer._tracer._exporter._writer.flush(() => {}) } catch {}
    }

    config () {
      const c = tracer._tracer?._config ?? {}
      const url = tracer._tracer?._url || c.url
      const m = new Map()
      const str = (v) => (v != null ? String(v) : 'null')
      m.set('dd_service', str(c.service))
      m.set('dd_env', str(c.tags?.env))
      m.set('dd_version', str(c.version))
      m.set('dd_trace_agent_url', url ? url.toString() : 'null')
      m.set('dd_trace_rate_limit', str(c.sampler?.rateLimit))
      m.set('dd_trace_sample_rate', str(c.sampleRate))
      m.set('dd_trace_enabled', c ? 'true' : 'false')
      m.set('dd_trace_propagation_style', c.tracePropagationStyle?.inject?.join(',') ?? 'null')
      m.set('dd_log_level', c.logLevel != null ? String(c.logLevel).toLowerCase() : 'null')
      m.set('dd_trace_debug', c.debug != null ? String(c.debug).toLowerCase() : 'null')
      const rtm = (c.runtimeMetrics && typeof c.runtimeMetrics === 'object') ? c.runtimeMetrics.enabled : c.runtimeMetrics
      m.set('dd_runtime_metrics_enabled', rtm != null ? String(rtm).toLowerCase() : 'null')
      m.set('dd_tags', c.tags != null ? Object.entries(c.tags).map(([k, v]) => `${k}:${v}`).join(',') : 'null')
      return m
    }

    #otelById = new Map()
    otelStartSpan (name, parentId, kind) {
      const k = otelApi.SpanKind[String(kind).toUpperCase()] ?? otelApi.SpanKind.INTERNAL
      let ctx
      if (parentId && parentId !== '0') {
        const otelParent = this.#otelById.get(parentId)
        if (otelParent) {
          ctx = otelApi.trace.setSpan(otelApi.context.active(), otelParent)
        } else {
          const ddParent = this.#byId.get(parentId)
          if (ddParent) {
            const pc = ddParent.context()
            const traceIdHex = pc._traceId.toString(16).padStart(32, '0')
            const spanIdHex = pc._spanId.toString(16).padStart(16, '0')
            ctx = otelApi.trace.setSpanContext(otelApi.context.active(),
              { traceId: traceIdHex, spanId: spanIdHex, traceFlags: 1, isRemote: false })
          }
        }
      }
      const span = otelTracer.startSpan(name, { kind: k }, ctx)
      const sc = span.spanContext()
      const sid = hexToDec(sc.spanId)
      const tid = hexToDec(sc.traceId.slice(-16))
      this.#otelById.set(sid, span)
      // register the dd view of this otel span so DD-API ops (setMeta/setMetric/
      // setResource/addLink) and span capture work on it too
      if (span._ddSpan) this.#byId.set(sid, span._ddSpan)
      return new CapturedSpan(tid, sid, parentId === '0' ? '0' : parentId, name, '', '', '', new Map(), new Map(), [])
    }
    otelSetAttribute (spanId, key, value) { this.#otelById.get(spanId)?.setAttribute(key, value) }
    otelAddEvent (spanId, name, timeMicros, attrs) {
      const s = this.#otelById.get(spanId)
      if (!s) return
      const coerce = (kind, v) =>
        kind === 'int' ? Number.parseInt(v, 10)
          : kind === 'double' ? Number.parseFloat(v)
            : kind === 'bool' ? (v === 'true') : v
      const invalid = { raw_mixed_arr: [1, 'a'], raw_nested_arr: [[1]], raw_huge_int: 2 ** 66 }
      const obj = {}
      for (const a of attrs) {
        if (a.kind in invalid) { obj[a.key] = invalid[a.kind]; continue }
        const vals = []
        for (const v of a.values) vals.push(v)
        if (a.kind.endsWith('_arr')) {
          const base = a.kind.slice(0, -4)
          obj[a.key] = vals.map((v) => coerce(base, v))
        } else {
          obj[a.key] = coerce(a.kind, vals[0] ?? '')
        }
      }
      // OTel JS expects the timestamp as epoch milliseconds; the test units are microseconds.
      s.addEvent(name, obj, timeMicros / 1000)
    }
    wireSpanEventsJson (spanId) {
      const f = this.#formatted.find((x) => dec10(x.span_id) === spanId)
      if (!f || !encoder || !msgpackDecode) return ''
      try {
        encoder.reset()
        encoder.encode([f])
        const buf = encoder.makePayload()
        const b = Array.isArray(buf) ? buf[0] : buf
        const traces = msgpackDecode(b, { useBigInt64: true })
        const repl = (k, v) => (typeof v === 'bigint' ? (v <= 9007199254740991n ? Number(v) : v.toString()) : v)
        for (const trace of traces) {
          for (const sp of trace) {
            if (sp && dec10(sp.span_id) === spanId && sp.span_events) {
              return JSON.stringify(sp.span_events, repl)
            }
          }
        }
      } catch {}
      return ''
    }
    wireSpanMetaEventsJson (spanId) {
      const f = this.#formatted.find((x) => dec10(x.span_id) === spanId)
      if (!f || !v05encoder || !msgpackDecode) return ''
      try {
        v05encoder.reset()
        v05encoder.encode([f])
        const buf = v05encoder.makePayload()
        const b = Array.isArray(buf) ? buf[0] : buf
        const dec = msgpackDecode(b, { useBigInt64: true })
        const strings = dec[0]
        for (const trace of dec[1]) {
          for (const sp of trace) {
            if (dec10(sp[4]) === spanId) {
              const meta = sp[9]
              const ent = meta instanceof Map ? [...meta.entries()] : Object.entries(meta)
              for (const [k, v] of ent) {
                if (strings[Number(k)] === 'events') return JSON.stringify(JSON.parse(strings[Number(v)]))
              }
            }
          }
        }
      } catch {}
      return ''
    }
    otelEndSpan (spanId) { this.#otelById.get(spanId)?.end() }
    otelIsRecording (spanId) { return this.#otelById.get(spanId)?.isRecording() ?? false }
    otelSpanContext (spanId) {
      const sc = this.#otelById.get(spanId).spanContext()
      return new OtelSpanContextInfo(sc.traceId, sc.spanId)
    }
    telemetryConfig () {
      return (capturedTelemetry ?? []).map((c) =>
        new TelemetryConfigItem(String(c.name), String(c.value), String(c.origin)))
    }

    otelSetStatus (spanId, code, description) {
      const s = this.#otelById.get(spanId)
      if (s) s.setStatus({ code: otelApi.SpanStatusCode[String(code).toUpperCase()] ?? otelApi.SpanStatusCode.UNSET, message: description })
    }
    otelRecordException (spanId, message, attributes) {
      const s = this.#otelById.get(spanId)
      if (!s) return
      const err = new Error(message)
      const st = attributes && (attributes.get ? attributes.get('exception.stacktrace') : attributes['exception.stacktrace'])
      if (st) err.stack = st
      s.recordException(err)
    }

    capturedSpans () {
      return this.#formatted.map((f) => {
        const sid = dec10(f.span_id)
        const meta = new Map()
        for (const k of Object.keys(f.meta ?? {})) meta.set(k, String(f.meta[k]))
        const metrics = new Map()
        for (const k of Object.keys(f.metrics ?? {})) {
          if (typeof f.metrics[k] === 'number') metrics.set(k, f.metrics[k])
        }
        // links are not in the formatted shape; read them from the live span
        const live = this.#byId.get(sid)
        const links = (live?._links ?? []).map((l) => {
          const attrs = new Map()
          for (const k of Object.keys(l.attributes ?? {})) attrs.set(k, String(l.attributes[k]))
          const tidHex = l.context?._trace?.tags?.['_dd.p.tid']
          const high = tidHex ? Number.parseInt(tidHex, 16) : 0
          return new CapturedLink(l.context.toSpanId(), l.context.toTraceId(), high, attrs)
        })
        return new CapturedSpan(
          dec10(f.trace_id), sid, dec10(f.parent_id), f.name ?? '',
          f.service ?? '', f.resource ?? '', f.type ?? '', meta, metrics, links,
          typeof f.error === 'number' ? f.error : 0,
        )
      })
    }
  }
  return new DdTraceAdapter()
}

// dd-trace + @opentelemetry/api are resolved from this adapter's node_modules
// (npm-installed), the same way the Python adapter uses a pip-installed ddtrace.
export let otelApi = null
try { otelApi = require('@opentelemetry/api') } catch {}
let msgpackDecode = null
try { msgpackDecode = require('@msgpack/msgpack').decode } catch {}
let V05Encoder = null
try { V05Encoder = require('dd-trace/packages/dd-trace/src/encode/0.5.js').AgentEncoder } catch {}

export function ddTraceVersion () {
  try { return require('dd-trace/package.json').version } catch { return null }
}

export function initTracer () {
  const tracer = require('dd-trace').init({ startupLogs: false })
  for (const p of ['express', 'http', 'dns', 'net']) {
    try { tracer.use(p, false) } catch {}
  }
  return tracer
}
