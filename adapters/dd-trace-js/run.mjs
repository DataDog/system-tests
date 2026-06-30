// Conformance runner for dd-trace-js.
//
//   npm --prefix adapters/dd-trace-js install   # once: installs dd-trace + @opentelemetry/api
//   temper build -b js
//   node adapters/dd-trace-js/run.mjs
//
// Iterates the ConformanceCase registry and runs each case in its own child
// process with the case's env applied — mirroring system-tests' container-per-
// env model, and sidestepping dd-trace's process-global init.
import { spawnSync, spawn, execSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import fs from 'node:fs'
import path from 'node:path'

const require = createRequire(import.meta.url)
const here = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(here, '..', '..')

function readJson (p) {
  try { return JSON.parse(fs.readFileSync(p, 'utf8')) } catch { return null }
}
function bail (msg) {
  console.error(`\n✗ ${msg}\n`)
  process.exit(2)
}

// --- startup diagnostics: make any environment hiccup self-explanatory ---
const generatedLib = path.join(repoRoot, 'temper.out/js/system-tests-redux/system_tests_redux.js')
const temperlangDir = path.join(repoRoot, 'temper.out/js/node_modules/@temperlang')
const corePkg = readJson(path.join(temperlangDir, 'core/package.json'))
let ddVersion = null
try { ddVersion = require('dd-trace/package.json').version } catch {}

console.log('— dd-trace-js conformance runner —')
console.log(`node:           ${process.version}  (${process.execPath})`)
console.log(`repo root:      ${repoRoot}`)
console.log(`generated lib:  ${fs.existsSync(generatedLib) ? 'present' : 'MISSING — run `temper build -b js`'}`)
console.log(`@temperlang:    ${fs.existsSync(temperlangDir)
  ? `core@${corePkg?.version ?? '?'}${corePkg?.imports ? ' (uses # imports!)' : ''}`
  : 'MISSING — `temper build -b js` did not install temper.out/js/node_modules'}`)
console.log(`dd-trace:       ${ddVersion ? `dd-trace@${ddVersion} (npm)` : '— NOT INSTALLED'}`)
console.log('')

// --- fail fast with actionable messages instead of a raw module error ---
if (!fs.existsSync(generatedLib)) bail('Generated library missing. Run `temper build -b js` from the repo root first.')
if (!fs.existsSync(temperlangDir)) bail('temper.out/js/node_modules/@temperlang is missing. Re-run `temper build -b js`; if it persists, delete temper.out and rebuild.')
if (!ddVersion) bail('dd-trace is not installed. Run `npm --prefix adapters/dd-trace-js install`.')

let lib
try {
  ({ lib } = await import('./adapter.mjs'))
} catch (e) {
  bail(`Failed to load the generated library or adapter:\n  ${e.stack ?? e.message}\nMost likely temper.out is stale — delete it and run \`temper build -b js\`.`)
}

const LIBRARY = 'nodejs'
const cases = lib.allCases()
let failed = 0
let skipped = 0

// Start a real ddapm-test-agent if any case needs the wire (delivered traces / stats).
const venvBin = path.join(repoRoot, '.venv-ddtrace', 'bin')
let agentProc = null
let agentUrl = null
const agentGet = (p) => {
  try { return execSync(`curl -s ${agentUrl}${p}`, { encoding: 'utf8', timeout: 4000 }) } catch { return null }
}
if (cases.some((c) => c.needsAgent)) {
  const port = parseInt(execSync(
    `${path.join(venvBin, 'python')} -c "import socket;s=socket.socket();s.bind(('127.0.0.1',0));print(s.getsockname()[1]);s.close()"`,
    { encoding: 'utf8' }).trim(), 10)
  agentUrl = `http://127.0.0.1:${port}`
  agentProc = spawn(path.join(venvBin, 'ddapm-test-agent'), ['--port', String(port)], { stdio: 'ignore' })
  for (let k = 0; k < 50; k++) {
    if (agentGet('/info')) break
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 200)
  }
}

cases.forEach((cse, i) => {
  if ([...cse.unsupported].includes(LIBRARY)) {
    console.log(`SKIP ${cse.name} (unsupported on ${LIBRARY})`)
    skipped++
    return
  }
  const env = { ...process.env }
  for (const [k, v] of cse.env) env[k] = v
  if (cse.needsAgent && agentUrl) {
    env.DD_TRACE_AGENT_URL = agentUrl
    agentGet('/test/session/clear')
  }
  const res = spawnSync(
    process.execPath,
    [path.join(here, 'run-one.mjs'), String(i)],
    { env, encoding: 'utf8' },
  )
  process.stdout.write(res.stdout ?? '')
  if (res.stderr) process.stderr.write(res.stderr)
  if (res.status !== 0) failed++
})

if (agentProc) agentProc.kill()

const ran = cases.length - skipped
console.log(`\n${ran - failed}/${ran} cases passed (dd-trace-js)${skipped ? `, ${skipped} skipped` : ''}`)
process.exit(failed ? 1 : 0)
