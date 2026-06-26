// Helper: init dd-trace with remote-config enabled (env carries DD_TRACE_AGENT_URL
// + DD_REMOTE_CONFIGURATION_ENABLED + DD_SERVICE/DD_ENV), let the async RC poller
// run for a moment so it advertises capabilities to the agent, then exit.
import { createRequire } from 'module'
const require = createRequire(import.meta.url)
const tracer = require('dd-trace').init({ startupLogs: false })
tracer.startSpan('rc-warmup').finish()
setTimeout(() => process.exit(0), Number(process.env.STR_RC_WAIT_MS || 2500))
