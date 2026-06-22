# AppSec with Restart Propagation - Root Cause Analysis

**Date:** January 9, 2026  
**Issue:** `APPSEC_WITH_RESTART_PROPAGATION` scenario failing for Java Spring-Boot weblog  
**Status:** Working for Node.js, Python, .NET | Failing for Java  
**Environment Variable:** `DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT=restart`

---

## 📋 Initial Investigation Request

### Problem Statement

I'm running the end-to-end scenario `APPSEC_WITH_RESTART_PROPAGATION` for Java with the Spring-Boot weblog, and it's failing. The scenario `APPSEC_WITHOUT_RESTART_PROPAGATION` is working correctly.

The `APPSEC_WITH_RESTART_PROPAGATION` scenario is working for other languages like Node.js, Python, and .NET. The environment property `DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT=restart` is causing unexpected behavior in Java.

### Investigation Objectives

After analyzing the test failures for the `APPSEC_WITH_RESTART_PROPAGATION` scenario, this document provides:

1. **Comparative Analysis** - How `DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT` with value `restart` works in:
   - `dd-trace-java` (failing)
   - `dd-trace-js` (working)
   - `dd-trace-py` (working)
   - `dd-trace-dotnet` (working)

2. **Deep Dive** - How the `DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT` environment property works across all tracers

3. **Proposed Solution** - Changes to `dd-trace-java` to fix the problem and align behavior with other tracers

---

## 🔍 Executive Summary

The `APPSEC_WITH_RESTART_PROPAGATION` scenario fails for Java because the tracer **resets propagation tags to empty** when in `restart` mode, which causes:
1. Loss of AppSec markers (`_dd.p.ts`, `_dd.p.appsec`)
2. Failure to set AppSec tags (`_dd.appsec.enabled`, `appsec.event`) on the root span
3. Missing request header collection metadata

Other tracers (Node.js, Python, .NET) preserve AppSec context independently and don't exhibit this issue.

---

## 📊 Test Results Comparison

### ❌ APPSEC_WITH_RESTART_PROPAGATION (Java - FAILING)

**Test Failures:**
- ❌ `Test_RetainTraces::test_appsec_event_span_tags` - Can't find `appsec.event` in span's meta
- ❌ `Test_AppSecEventSpanTags::test_custom_span_tags` - Cannot find `_dd.appsec.enabled` in span metrics
- ❌ `Test_AppSecEventSpanTags::test_header_collection` - Missing request headers
- ❌ `Test_AppSecEventSpanTags::test_root_span_coherence` - No appsec-enabled spans found

**Trace Data (Attack Span):**
```json
{
  "trace_id": 5780561985243503222,
  "span_id": 2290079944842805273,
  "parent_id": 0,  // ← New root span (restart mode)
  "type": "web",
  "meta": {
    "_dd.p.dm": "-1",
    "_dd.p.tid": "6960b1eb00000000",
    "_dd.integration": "tomcat-server",
    "_dd.span_links": "[{\"span_id\":\"0\",\"trace_id\":\"00000000000000000000000000000000\"}]",
    "http.useragent": "Arachni/v1 rid/BAYFDWODPLAKUZCVYMBCGBQMTQTQBORQBYXF"
    // ❌ MISSING: "appsec.event"
    // ❌ MISSING: "http.request.headers.user-agent"
    // ❌ MISSING: "http.request.headers.host"
    // ❌ MISSING: "http.request.headers.content-type"
    // ❌ MISSING: "_dd.runtime_family"
  },
  "metrics": {
    "_sampling_priority_v1": 1,  // ❌ NOT upgraded to 2
    "_dd.measured": 1,
    "_dd.top_level": 1
    // ❌ MISSING: "_dd.appsec.enabled"
  }
}
```

### ✅ APPSEC_WITHOUT_RESTART_PROPAGATION (Java - WORKING)

**Test Results:** All tests passing

**Trace Data (Attack Span):**
```json
{
  "trace_id": 3583981281136459325,
  "span_id": 5808736898340159070,
  "parent_id": 0,
  "type": "web",
  "meta": {
    "_dd.p.ts": "02",  // ✅ AppSec trace source marker
    "_dd.p.dm": "-5",
    "_dd.integration": "tomcat-server",
    "✅ appsec.event": "true",  // ✅ Present!
    "✅ http.request.headers.user-agent": "Arachni/v1 rid/NKNRICFJWUXRLSTQYMCYQUNUVNSEIGYWBSUX",
    "✅ http.request.headers.host": "localhost:7777",
    "✅ http.request.headers.accept-encoding": "identity",
    "✅ http.request.headers.content-type": "text/plain",
    "✅ _dd.runtime_family": "jvm",
    "✅ actor.ip": "172.18.0.1",
    "_dd.appsec.json": { /* security event data */ }
  },
  "metrics": {
    "_sampling_priority_v1": 2,  // ✅ Correctly upgraded to USER_KEEP
    "✅ _dd.appsec.enabled": 1,  // ✅ Present!
    "_dd.appsec.waf.duration": 127,
    "_dd.measured": 1,
    "_dd.top_level": 1
  }
}
```

### ✅ APPSEC_WITH_RESTART_PROPAGATION (Node.js, Python, .NET - WORKING)

All other language tracers pass the tests successfully with `restart` mode enabled.

---

## 🎯 Understanding DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT

### Configuration

**Environment Variable:** `DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT`  
**System Property (Java):** `dd.trace.propagation.behavior.extract`  
**Default Value:** `continue`  
**Possible Values:** `continue`, `restart`, `ignore`

### Behavior Modes

| Mode | Continues Trace? | Preserves Baggage? | Creates Span Links? | AppSec Context |
|------|------------------|-------------------|---------------------|----------------|
| **continue** (default) | ✅ Yes | ✅ Yes | Only for conflicts | ✅ Preserved |
| **restart** | ❌ No - New trace | ✅ Yes | ✅ Yes | ⚠️ Should preserve |
| **ignore** | ❌ No - New trace | ❌ No | ❌ No | ❌ Lost |

### Expected Behavior with `restart`

When `DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT=restart` is set:

1. **Extracts trace context** from incoming headers (Datadog, W3C TraceContext, etc.)
2. **Starts a NEW trace** - Generates new trace ID, sets parent_id=0
3. **Preserves baggage** - W3C baggage items are carried forward
4. **Creates span link** - Original context preserved as span link with:
   - `reason: "propagation_behavior_extract"`
   - `context_headers: <style>` (e.g., "datadog", "tracecontext")
5. **Independent sampling** - New trace makes its own sampling decision

---

## 🔬 Tracer Implementation Comparison

### dd-trace-java Implementation

**Location:** `CoreTracer.java`, lines 1752-1768

```java
// Handle remote terminated context as span links
if (parentContext != null && parentContext.isRemote()) {
  switch (Config.get().getTracePropagationBehaviorExtract()) {
    case RESTART:
      links = addParentContextLink(links, parentContext);
      parentContext = null;  // ← KEY: Break parent link, start new trace
      break;

    case IGNORE:
      parentContext = null;
      break;

    case CONTINUE:
    default:
      links = addTerminatedContextAsLinks(links, specifiedParentContext);
      break;
  }
}
```

**Span Construction with RESTART (lines 1978-2005):**

```java
// After restart, parentContext becomes null, so we fall through to:
} else {
  // Start a new trace
  traceId = tracer.idGenerationStrategy.generateTraceId();  // ← NEW trace ID
  parentSpanId = DDSpanId.ZERO;
  samplingPriority = PrioritySampling.UNSET;
  endToEndStartTime = 0;
  propagationTags = tracer.propagationTagsFactory.empty();  // ← ❌ RESETS TO EMPTY!
}
```

**⚠️ PROBLEM:** Propagation tags (including `_dd.p.ts` for AppSec) are **reset to empty**.

**When CONTINUE (lines 1982-1989):**

```java
if (resolvedParentContext instanceof ExtractedContext) {
  final ExtractedContext extractedContext = (ExtractedContext) resolvedParentContext;
  traceId = extractedContext.getTraceId();  // ← Continues trace
  parentSpanId = extractedContext.getSpanId();
  samplingPriority = extractedContext.getSamplingPriority();
  propagationTags = extractedContext.getPropagationTags();  // ← ✅ PRESERVES propagation tags
}
```

### dd-trace-js Implementation

**Location:** `packages/dd-trace/src/opentracing/propagation/text_map.js`, lines 379-388

```javascript
if (this._config.tracePropagationBehaviorExtract === 'restart') {
  context._links = []
  context._links.push({
    context,  // ← Preserves original context in span link
    attributes: {
      reason: 'propagation_behavior_extract', 
      context_headers: style
    }
  })
}
this._extractBaggageItems(carrier, context)
```

**Location:** `packages/dd-trace/src/opentracing/span.js`, lines 336-377

```javascript
let baggage = {}
if (parent && parent._isRemote && this._parentTracer?._config?.tracePropagationBehaviorExtract !== 'continue') {
  baggage = parent._baggageItems  // ← Preserves baggage
  parent = null  // Detach from the parent
}

// Later, if creating a new root span and restart mode:
if (this._parentTracer?._config?.tracePropagationBehaviorExtract === 'restart') {
  spanContext._baggageItems = baggage  // ← Restores baggage items
}
```

**✅ KEY DIFFERENCE:** Node.js still extracts and processes baggage, and AppSec tags are set **independently of parent context**.

### dd-trace-py Implementation

**Location:** `ddtrace/propagation/http.py`, lines 1262-1264

```python
if config._propagation_behavior_extract == _PROPAGATION_BEHAVIOR_RESTART:
    link = HTTPPropagator._context_to_span_link(context, style, "propagation_behavior_extract")
    context = Context(
        baggage=context.get_all_baggage_items(),  # ← Preserves baggage
        span_links=[link] if link else []  # ← Creates span link
    )
```

**✅ KEY DIFFERENCE:** Python creates a **new context with preserved baggage** and span links, and AppSec tags are set **on the new root span without dependency on propagation tags**.

---

## 🐛 Root Cause: Java-Specific Issues

### Problem #1: Propagation Tags Reset

**Impact:** The `_dd.p.ts` (trace source) tag containing the AppSec marker (0x02) is **completely lost**.

```java
// ProductTraceSource.java
public static final int APM = 0x01;
public static final int ASM = 0x02;  // AppSec marker
public static final int DSM = 0x04;
public static final int DJM = 0x08;
public static final int DBM = 0x10;
```

**Encoded as 2-character hex:**
- `"01"` = APM only
- `"02"` = AppSec only
- `"03"` = APM + AppSec

**Propagated via:** `_dd.p.ts` tag in span metadata and `x-datadog-tags` header

### Problem #2: AppSec Tag Setting Depends on Root Span

**Location:** `GatewayBridge.java`, lines 850-871

```java
TraceSegment traceSeg = ctx_.getTraceSegment();

// Tags are set on TraceSegment, which routes to root span
traceSeg.setTagTop("_dd.appsec.enabled", 1);  // ← Requires root span via TraceCollector
traceSeg.setTagTop("_dd.runtime_family", "jvm");

// If security events detected
if (!collectedEvents.isEmpty()) {
    traceSeg.setTagTop("appsec.event", true);  // ← Requires root span via TraceCollector
    traceSeg.setTagTop("network.client.ip", ctx.getPeerAddress());
    traceSeg.setDataTop("appsec", wrapper);  // AppSec events as structured data
}
```

**Location:** `DDSpanContext.java`, lines 1221-1222

```java
@Override
public void setTagTop(String key, Object value, boolean sanitize) {
    getRootSpanContextOrThis().setTagCurrent(key, value, sanitize);
}

private DDSpanContext getRootSpanContextIfDifferent() {
    if (traceCollector != null) {
        final DDSpan rootSpan = traceCollector.getRootSpan();  // ← Needs root span!
        if (null != rootSpan && rootSpan.context() != this) {
            return rootSpan.context();
        }
    }
    return null;
}
```

**⚠️ PROBLEM:** When `restart` mode breaks the parent context and starts a new trace, the `TraceCollector` may not have properly initialized the root span reference when AppSec attempts to set tags during the request lifecycle.

### Problem #3: Sampling Priority Logic

**Location:** `TraceCollector.java`, lines 67-74

```java
// Ignore the force-keep priority in the absence of propagated _dd.p.ts span tag marked for ASM.
if ((!Config.get().isApmTracingEnabled()
        && !ProductTraceSource.isProductMarked(
            rootSpan.context().getPropagationTags().getTraceSource(), ProductTraceSource.ASM))
    || rootSpan.context().getSamplingPriority() == PrioritySampling.UNSET) {
    ((PrioritySampler) traceConfig.sampler).setSamplingPriority(rootSpan);
}
```

**⚠️ PROBLEM:** Since `propagationTags` is reset to empty in `restart` mode, the `_dd.p.ts` tag is missing, causing sampling logic to potentially ignore AppSec force-keep priority.

---

## 🔧 Proposed Fixes for dd-trace-java

### Fix #1: Preserve AppSec Propagation Tags in Restart Mode

**Modify:** `CoreTracer.java` around lines 1754-1768

```java
case RESTART:
    links = addParentContextLink(links, parentContext);
    
    // ✨ FIX: Preserve AppSec-related propagation tags
    PropagationTags preservedAppSecTags = null;
    if (parentContext instanceof ExtractedContext) {
        ExtractedContext extractedContext = (ExtractedContext) parentContext;
        PropagationTags originalTags = extractedContext.getPropagationTags();
        if (originalTags != null && 
            ProductTraceSource.isProductMarked(originalTags.getTraceSource(), ProductTraceSource.ASM)) {
            preservedAppSecTags = extractAppSecPropagationTags(originalTags);
        }
    }
    
    parentContext = null;
    break;
```

**Add new method:**

```java
/**
 * Extracts only AppSec-related propagation tags for preservation in restart mode.
 * This ensures AppSec context is maintained even when breaking trace continuity.
 *
 * @param original The original propagation tags from the extracted context
 * @return PropagationTags containing only AppSec markers, or empty if no AppSec context
 */
private PropagationTags extractAppSecPropagationTags(PropagationTags original) {
    if (original == null || original.getTraceSource() == 0) {
        return tracer.propagationTagsFactory.empty();
    }
    
    int traceSource = original.getTraceSource();
    
    // Only preserve if ASM (AppSec) bit is set
    if (ProductTraceSource.isProductMarked(traceSource, ProductTraceSource.ASM)) {
        // Create propagation tags with only the trace source preserved
        Map<String, String> tags = new HashMap<>();
        tags.put("_dd.p.ts", String.format("%02x", traceSource));
        
        // Optionally preserve the appsec marker
        if (original.containsTag("_dd.p.appsec")) {
            tags.put("_dd.p.appsec", "1");
        }
        
        return tracer.propagationTagsFactory.fromMap(tags);
    }
    
    return tracer.propagationTagsFactory.empty();
}
```

**Modify span construction (around line 2005):**

```java
} else {
    // Start a new trace
    traceId = tracer.idGenerationStrategy.generateTraceId();
    parentSpanId = DDSpanId.ZERO;
    samplingPriority = PrioritySampling.UNSET;
    endToEndStartTime = 0;
    
    // ✨ FIX: Use preserved AppSec tags instead of empty when in restart mode
    propagationTags = (preservedAppSecTags != null) 
        ? preservedAppSecTags 
        : tracer.propagationTagsFactory.empty();
}
```

### Fix #2: Ensure AppSec Tags Are Set on Root Span (Defensive)

**Modify:** `GatewayBridge.java` around line 850

```java
TraceSegment traceSeg = ctx_.getTraceSegment();

if (traceSeg != null) {
    // ✨ FIX: Ensure we have a valid root span before setting tags
    // Add retry mechanism with fallback to current span
    try {
        traceSeg.setTagTop("_dd.appsec.enabled", 1);
        traceSeg.setTagTop("_dd.runtime_family", "jvm");
    } catch (Exception e) {
        // Fallback: set on current span if root span resolution fails
        log.debug("Failed to set AppSec tags on root span, setting on current span", e);
        traceSeg.setTagCurrent("_dd.appsec.enabled", 1);
        traceSeg.setTagCurrent("_dd.runtime_family", "jvm");
    }
    
    Collection<AppSecEvent> collectedEvents = ctx.transferCollectedEvents();
    
    if (!collectedEvents.isEmpty()) {
        try {
            if (ctx.isManuallyKept()) {
                traceSeg.setTagTop(Tags.ASM_KEEP, true);
                traceSeg.setTagTop(Tags.PROPAGATED_TRACE_SOURCE, ProductTraceSource.ASM);
            }
            traceSeg.setTagTop("appsec.event", true);
            traceSeg.setTagTop("network.client.ip", ctx.getPeerAddress());
        } catch (Exception e) {
            // Fallback for security event tags
            log.warn("Failed to set AppSec event tags on root span", e);
            traceSeg.setTagCurrent("appsec.event", true);
            traceSeg.setTagCurrent("network.client.ip", ctx.getPeerAddress());
        }
    }
}
```

### Fix #3: Alternative - Deferred Tag Setting

**Modify:** `AppSecRequestContext.java`

Add mechanism to store tags that should be set on the root span and apply them later when the root span is definitely available:

```java
public class AppSecRequestContext {
    private final Map<String, Object> pendingRootSpanTags = new ConcurrentHashMap<>();
    private final Map<String, Object> pendingRootSpanData = new ConcurrentHashMap<>();
    
    /**
     * Queue a tag to be set on the root span when it's available.
     * This allows AppSec instrumentation to work correctly even when
     * the root span hasn't been fully initialized yet (e.g., in restart mode).
     */
    public void queueRootSpanTag(String key, Object value) {
        pendingRootSpanTags.put(key, value);
    }
    
    /**
     * Queue structured data to be set on the root span when it's available.
     */
    public void queueRootSpanData(String key, Object value) {
        pendingRootSpanData.put(key, value);
    }
    
    /**
     * Commit all pending root span tags and data.
     * Called when the root span is known to be available.
     */
    public void commitPendingRootSpanTags(TraceSegment traceSegment) {
        if (!pendingRootSpanTags.isEmpty()) {
            for (Map.Entry<String, Object> entry : pendingRootSpanTags.entrySet()) {
                try {
                    traceSegment.setTagTop(entry.getKey(), entry.getValue());
                } catch (Exception e) {
                    log.debug("Failed to set pending tag on root span: " + entry.getKey(), e);
                    // Fallback to current span
                    traceSegment.setTagCurrent(entry.getKey(), entry.getValue());
                }
            }
            pendingRootSpanTags.clear();
        }
        
        if (!pendingRootSpanData.isEmpty()) {
            for (Map.Entry<String, Object> entry : pendingRootSpanData.entrySet()) {
                try {
                    traceSegment.setDataTop(entry.getKey(), entry.getValue());
                } catch (Exception e) {
                    log.debug("Failed to set pending data on root span: " + entry.getKey(), e);
                    traceSegment.setDataCurrent(entry.getKey(), entry.getValue());
                }
            }
            pendingRootSpanData.clear();
        }
    }
}
```

**Modify:** `GatewayBridge.java`

```java
private NoopFlow onRequestEnded(RequestContext ctx_, IGSpanInfo spanInfo) {
    AppSecRequestContext ctx = ctx_.getData(RequestContextSlot.APPSEC);
    if (ctx == null) {
        return NoopFlow.INSTANCE;
    }
    
    TraceSegment traceSeg = ctx_.getTraceSegment();
    
    if (traceSeg != null) {
        // ✨ Queue tags instead of setting directly
        ctx.queueRootSpanTag("_dd.appsec.enabled", 1);
        ctx.queueRootSpanTag("_dd.runtime_family", "jvm");
        
        Collection<AppSecEvent> collectedEvents = ctx.transferCollectedEvents();
        
        if (!collectedEvents.isEmpty()) {
            if (ctx.isManuallyKept()) {
                ctx.queueRootSpanTag(Tags.ASM_KEEP, true);
                ctx.queueRootSpanTag(Tags.PROPAGATED_TRACE_SOURCE, ProductTraceSource.ASM);
            }
            ctx.queueRootSpanTag("appsec.event", true);
            ctx.queueRootSpanTag("network.client.ip", ctx.getPeerAddress());
            
            // Queue AppSec data
            ctx.queueRootSpanData("appsec", createAppSecData(collectedEvents));
        }
        
        // ✨ Commit all pending tags - root span should be available by now
        ctx.commitPendingRootSpanTags(traceSeg);
        
        // ... rest of processing
    }
    
    return NoopFlow.INSTANCE;
}
```

---

## 📈 Impact Analysis

### Current Impact

**Severity:** HIGH - AppSec functionality completely broken in restart mode

**Affected Scenarios:**
- Services using `DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT=restart` with AppSec enabled
- Distributed tracing across service boundaries with restart behavior
- Security event correlation and trace retention

**Test Coverage:**
- 4 out of 4 tests failing for `APPSEC_WITH_RESTART_PROPAGATION` scenario
- Tests passing for `APPSEC_WITHOUT_RESTART_PROPAGATION` scenario
- Tests passing for other languages (Node.js, Python, .NET)

### Benefits of Fixing

1. **Consistent behavior** across all Datadog tracers
2. **Preserved security context** even when breaking trace continuity
3. **Correct sampling decisions** for traces with security events
4. **Improved observability** for AppSec events in distributed systems
5. **Support for service boundary patterns** without losing security context

---

## 🧪 Testing Strategy

### Test Cases to Verify Fix

1. **Basic AppSec Tags in Restart Mode**
   - Verify `_dd.appsec.enabled` is set on root span
   - Verify `_dd.runtime_family` is set on root span
   - Verify `appsec.event` is set when attack is detected

2. **Propagation Tags Preservation**
   - Verify `_dd.p.ts=02` is preserved in restart mode
   - Verify `_dd.p.appsec=1` is preserved in restart mode
   - Verify downstream services receive AppSec propagation tags

3. **Sampling Priority**
   - Verify sampling priority upgraded to 2 (USER_KEEP) when AppSec event occurs
   - Verify traces with security events are retained

4. **Header Collection**
   - Verify request headers are collected and set on span metadata
   - Verify response headers are collected and set on span metadata

5. **Span Links**
   - Verify span link is created with original trace context
   - Verify span link includes `reason: "propagation_behavior_extract"`
   - Verify span link includes `context_headers: "datadog"`

### Test Execution

```bash
# Run APPSEC_WITH_RESTART_PROPAGATION scenario for Java
TEST_LIBRARY=java ./run.sh APPSEC_WITH_RESTART_PROPAGATION

# Run specific test class
TEST_LIBRARY=java ./run.sh APPSEC_WITH_RESTART_PROPAGATION \
  tests/appsec/test_traces.py::Test_AppSecEventSpanTags

# Compare with APPSEC_WITHOUT_RESTART_PROPAGATION
TEST_LIBRARY=java ./run.sh APPSEC_WITHOUT_RESTART_PROPAGATION

# Test other languages for regression
TEST_LIBRARY=nodejs ./run.sh APPSEC_WITH_RESTART_PROPAGATION
TEST_LIBRARY=python ./run.sh APPSEC_WITH_RESTART_PROPAGATION
TEST_LIBRARY=dotnet ./run.sh APPSEC_WITH_RESTART_PROPAGATION
```

---

## 📚 References

### System Tests Documentation
- **Scenario Definition:** `utils/_context/_scenarios/__init__.py` (lines 1154-1166)
- **Test File:** `tests/appsec/test_traces.py`
- **Scenario Documentation:** `docs/scenarios/README.md`
- **End-to-End Testing:** `docs/execute/run.md`

### dd-trace-java Source Code
- **CoreTracer:** Trace propagation restart behavior (lines 1752-1768, 1978-2005)
- **GatewayBridge:** AppSec event handling (lines 822-933)
- **DDSpanContext:** Root span resolution (lines 555-568, 1221-1295)
- **TraceCollector:** Sampling priority logic (lines 67-74)
- **PropagationTags:** Distributed context propagation
- **ProductTraceSource:** Product markers for trace source

### dd-trace-js Source Code
- **text_map.js:** Context extraction with restart (lines 379-388)
- **span.js:** Baggage preservation (lines 336-377)

### dd-trace-py Source Code
- **http.py:** Restart behavior implementation (lines 1262-1264)

### Slack Support
- **Channel:** `#apm-shared-testing`
- **Team:** `@DataDog/asm-libraries`

---

## ✅ Recommendations

### Immediate Actions

1. **Implement Fix #1** (Preserve AppSec Propagation Tags) - This is the primary fix that addresses the root cause
2. **Add defensive code** from Fix #2 to handle edge cases during span initialization
3. **Run full test suite** to verify no regressions

### Long-term Improvements

1. **Standardize restart behavior** across all Datadog tracers
2. **Document AppSec interaction** with trace propagation modes
3. **Add integration tests** specifically for AppSec + restart mode combinations
4. **Consider RFC** for standard restart behavior across all products

### Alternative Approaches

If preserving propagation tags has performance concerns:

1. Use Fix #3 (deferred tag setting) to decouple AppSec from span initialization timing
2. Create a separate AppSec context propagation mechanism independent of trace propagation
3. Use out-of-band security event correlation via distributed tracing metadata

---

## 📊 Appendix: Complete Trace Comparison

### Trace with RESTART (Java - Broken)

```json
{
  "service": "weblog",
  "name": "servlet.request",
  "resource": "GET /waf/**",
  "trace_id": 5780561985243503222,
  "span_id": 2290079944842805273,
  "parent_id": 0,
  "start": 1767944683408557794,
  "duration": 2158125,
  "type": "web",
  "error": 0,
  "metrics": {
    "_sampling_priority_v1": 1,
    "_dd.measured": 1,
    "_dd.top_level": 1,
    "thread.id": 98,
    "process_id": 1,
    "_dd.profiling.enabled": 0,
    "_dd.trace_span_attribute_schema": 0,
    "_dd.dsm.enabled": 1,
    "_dd.agent_psr": 1.0,
    "peer.port": 57826,
    "_dd.iast.enabled": 0
  },
  "meta": {
    "_dd.p.dm": "-1",
    "_dd.p.tid": "6960b1eb00000000",
    "thread.name": "http-nio-7777-exec-6",
    "http.status_code": "200",
    "key1": "val1",
    "key2": "val2",
    "_dd.tracer_host": "weblog",
    "http.url": "http://localhost:7777/waf/",
    "language": "jvm",
    "http.client_ip": "172.18.0.1",
    "_dd.integration": "tomcat-server",
    "span.kind": "server",
    "_dd.span_links": "[{\"span_id\":\"0\",\"trace_id\":\"00000000000000000000000000000000\"}]",
    "runtime-id": "dbc6308b-df00-4bd9-89c0-254897c30a1c",
    "http.method": "GET",
    "servlet.path": "/waf/",
    "env": "system-tests",
    "version": "1.0.0",
    "peer.ipv4": "172.18.0.1",
    "http.hostname": "localhost",
    "component": "tomcat-server",
    "servlet.context": "/",
    "http.route": "/waf/**",
    "http.useragent": "Arachni/v1 rid/BAYFDWODPLAKUZCVYMBCGBQMTQTQBORQBYXF"
  }
}
```

### Trace without RESTART (Java - Working)

```json
{
  "service": "weblog",
  "name": "servlet.request",
  "resource": "GET /waf/**",
  "trace_id": 3583981281136459325,
  "span_id": 5808736898340159070,
  "parent_id": 0,
  "start": 1767945150809430419,
  "duration": 2377334,
  "type": "web",
  "error": 0,
  "metrics": {
    "_sampling_priority_v1": 2,
    "_dd.measured": 1,
    "_dd.top_level": 1,
    "thread.id": 96,
    "_dd.iast.telemetry.executed.sink.session_rewriting": 16,
    "_dd.iast.telemetry.executed.sink.directory_listing_leak": 20,
    "_dd.iast.telemetry.executed.sink.hsts_header_missing": 6,
    "_dd.iast.telemetry.executed.sink.insecure_jsp_layout": 20,
    "_dd.appsec.waf.duration": 127,
    "_dd.trace_span_attribute_schema": 0,
    "_dd.appsec.waf.duration_ext": 290,
    "_dd.iast.telemetry.executed.sink.admin_console_active": 20,
    "_dd.iast.telemetry.executed.sink.xss": 1,
    "_dd.iast.telemetry.executed.sink.insecure_cookie": 6,
    "_dd.iast.enabled": 1,
    "_dd.iast.telemetry.executed.sink.unvalidated_redirect": 7,
    "_dd.appsec.enabled": 1,
    "_dd.iast.telemetry.executed.sink.default_app_deployed": 20,
    "process_id": 1,
    "_dd.iast.telemetry.executed.sink.no_httponly_cookie": 6,
    "_dd.iast.telemetry.executed.source.http_request_header": 16,
    "_dd.profiling.enabled": 0,
    "_dd.iast.telemetry.executed.sink.session_timeout": 20,
    "_dd.iast.telemetry.executed.sink.header_injection": 6,
    "_dd.iast.telemetry.executed.source.http_request_matrix_parameter": 2,
    "_dd.iast.telemetry.executed.sink.no_samesite_cookie": 6,
    "_dd.dsm.enabled": 1,
    "peer.port": 63196,
    "_dd.iast.telemetry.executed.source.http_request_query": 1,
    "_dd.iast.telemetry.executed.sink.xcontenttype_header_missing": 6,
    "_dd.iast.telemetry.executed.source.http_request_path": 1,
    "_dd.iast.telemetry.executed.sink.verb_tampering": 20,
    "_dd.iast.telemetry.executed.sink.default_html_escape_invalid": 20,
    "_dd.iast.telemetry.request.tainted": 1
  },
  "meta": {
    "_dd.p.ts": "02",
    "_dd.p.dm": "-5",
    "_dd.p.tid": "6960b3be00000000",
    "thread.name": "http-nio-7777-exec-4",
    "http.status_code": "200",
    "key1": "val1",
    "key2": "val2",
    "http.url": "http://localhost:7777/waf/",
    "language": "jvm",
    "http.client_ip": "172.18.0.1",
    "_dd.integration": "tomcat-server",
    "_dd.appsec.fp.http.header": "hdr-0010000000-04ed1cbb-1-4740ae63",
    "version": "1.0.0",
    "network.client.ip": "172.18.0.1",
    "peer.ipv4": "172.18.0.1",
    "http.hostname": "localhost",
    "_dd.appsec.event_rules.version": "1.13.3",
    "http.request.headers.host": "localhost:7777",
    "_dd.appsec.json": {
      "triggers": [
        {
          "rule": {
            "id": "ua0-600-12x",
            "name": "Arachni",
            "tags": {
              "type": "attack_tool",
              "category": "attack_attempt",
              "confidence": "1",
              "module": "waf",
              "tool_name": "Arachni",
              "cwe": "200",
              "capec": "1000/118/169"
            }
          },
          "rule_matches": [
            {
              "operator": "match_regex",
              "operator_value": "^Arachni\\/v",
              "parameters": [
                {
                  "address": "server.request.headers.no_cookies",
                  "highlight": ["Arachni/v"],
                  "key_path": ["user-agent", "0"],
                  "value": "Arachni/v1 rid/NKNRICFJWUXRLSTQYMCYQUNUVNSEIGYWBSUX"
                }
              ]
            }
          ],
          "span_id": 5808736898340159070
        }
      ]
    },
    "http.useragent": "Arachni/v1 rid/NKNRICFJWUXRLSTQYMCYQUNUVNSEIGYWBSUX",
    "_dd.tracer_host": "weblog",
    "http.request.headers.accept-encoding": "identity",
    "span.kind": "server",
    "runtime-id": "919ae0b3-20df-4530-8554-78dd5e692d93",
    "_dd.appsec.fp.http.endpoint": "http-get-ce4235d7--",
    "http.method": "GET",
    "actor.ip": "172.18.0.1",
    "appsec.event": "true",
    "http.response.headers.content-length": "12",
    "servlet.path": "/waf/",
    "env": "system-tests",
    "http.request.headers.user-agent": "Arachni/v1 rid/NKNRICFJWUXRLSTQYMCYQUNUVNSEIGYWBSUX",
    "component": "tomcat-server",
    "http.response.headers.content-type": "text/plain;charset=UTF-8",
    "_dd.appsec.fp.http.network": "net-0-0000000000",
    "servlet.context": "/",
    "http.route": "/waf/**",
    "_dd.runtime_family": "jvm"
  }
}
```

---

**Document Version:** 1.0  
**Last Updated:** January 9, 2026  
**Author:** System Tests Analysis  
**Status:** Analysis Complete - Awaiting Implementation

