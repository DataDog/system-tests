// Runs a single conformance case by index, against an npm-installed dd-trace
// initialized under this process's env (set by the parent runner). Prints one
// PASS/FAIL line and exits non-zero on failure.
import { lib, makeAdapter, initTracer, otelApi } from './adapter.mjs'

const index = Number(process.argv[2])

const cases = lib.allCases()
const cse = cases[index]
if (!cse) {
  console.error(`no case at index ${index}`)
  process.exit(2)
}

const tracer = initTracer()
const adapter = makeAdapter(tracer, otelApi)
const run = cse.run
const r = run(adapter)
if (r.ok) {
  console.log(`PASS ${cse.name}`)
  process.exit(0)
} else {
  console.log(`FAIL ${cse.name}:\n${r.summary()}`)
  process.exit(1)
}
