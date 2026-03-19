#!/usr/bin/env node
// Child process for spawn_child endpoint. Args: sleep (seconds), crash (true|false).
const sleepSec = parseInt(process.argv[2] || '2', 10) * 1000
const crash = process.argv[3] === 'true'
setTimeout(() => {
  if (crash) {
    process.kill(process.pid, 'SIGSEGV')
  } else {
    process.exit(0)
  }
}, sleepSec)
