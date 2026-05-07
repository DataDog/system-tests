'use strict'

// Time to wait after invoking dd-trace's beforeExit handlers before forcing
// the process to exit. The handlers are fire-and-forget (no Promise, no
// awaitable signal) and initiate asynchronous HTTP exports for telemetry,
// traces, remote config, AppSec metrics, dogstatsd, etc., so we need a grace
// window for those in-flight requests to drain. Same as docker stop's default
// 10s SIGKILL timeout.
const SHUTDOWN_GRACE_MS = 10000

function shutdown () {
  const ddTrace = globalThis[Symbol.for('dd-trace')]

  if (ddTrace?.beforeExitHandlers) {
    for (const handler of ddTrace.beforeExitHandlers) {
      try {
        handler()
      } catch (err) {
        // Best-effort: keep running other handlers even if one throws.
        console.error('dd-trace beforeExit handler threw', err)
      }
    }
  }

  setTimeout(() => process.exit(0), SHUTDOWN_GRACE_MS).unref()
}

export function register () {
  if (!process.env.NEXT_MANUAL_SIG_HANDLE || process.env.NEXT_RUNTIME === 'edge') return

  process.once('SIGINT', shutdown)
  process.once('SIGTERM', shutdown)
}
