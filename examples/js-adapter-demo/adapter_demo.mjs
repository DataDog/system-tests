// Native JS adapter demo — simulates what a dd-trace-js `system-tests-temper-adapter`
// would do: implement the Temper-generated `Tracer` interface against the real
// tracer, capture emitted spans in-memory, and run the compiled conformance test.
import {
  Tracer, CapturedSpan, CapturedLink, runSpanWithAttachedLinks,
} from "./system_tests_redux.js";

class NativeAdapter extends Tracer {
  #nextId = 1;
  #byId = new Map();   // id -> {traceId, spanId, parentId, name, service, resource, spanType, links, meta, metrics}
  #order = [];

  startSpan(name, parentId, service = "", resource = "", spanType = "") {
    const id = String(this.#nextId++);
    let traceId = id;
    if (parentId !== "0" && this.#byId.has(parentId)) {
      traceId = this.#byId.get(parentId).traceId;
    }
    const s = {
      traceId, spanId: id, parentId, name, service, resource, spanType,
      links: [], meta: new Map(), metrics: new Map(),
    };
    this.#byId.set(id, s);
    this.#order.push(s);
    return new CapturedSpan(traceId, id, parentId, name, service, resource, spanType,
      new Map(), new Map(), []);
  }
  finishSpan(_spanId) {}
  setMeta(spanId, key, value) { this.#byId.get(spanId).meta.set(key, value); }
  setMetric(spanId, key, value) { this.#byId.get(spanId).metrics.set(key, value); }
  addLink(spanId, linkToSpanId, attributes) {
    const target = this.#byId.get(linkToSpanId);
    // attributes is the Temper Map passed by the test; store & echo back as-is.
    this.#byId.get(spanId).links.push(
      new CapturedLink(target.spanId, target.traceId, 0, attributes),
    );
  }
  flush() {}
  capturedSpans() {
    return this.#order.map((s) =>
      new CapturedSpan(s.traceId, s.spanId, s.parentId, s.name, s.service, s.resource,
        s.spanType, s.meta, s.metrics, s.links));
  }
}

const r = runSpanWithAttachedLinks(new NativeAdapter());
if (r.ok) {
  console.log("PASS: runSpanWithAttachedLinks against NativeAdapter");
  process.exit(0);
} else {
  console.log("FAIL:\n" + r.summary());
  process.exit(1);
}
