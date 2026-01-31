'use strict'

// Minimal app to test dd-trace works without OpenFeature installed.
// See: https://github.com/DataDog/dd-trace-js/issues/6986

const tracer = require('dd-trace').init()
const app = require('express')()

app.get('/', (req, res) => {
  res.send('Hello\n')
})

app.get('/healthcheck', (req, res) => {
  res.json({
    status: 'ok',
    library: {
      name: 'nodejs',
      version: require('dd-trace/package.json').version
    }
  })
})

app.get('/flush', (req, res) => {
  tracer.dogstatsd?.flush?.()
  const timeout = Number(req.query.timeout) || 5000
  const start = Date.now()
  let interval

  function onFlush () {
    clearInterval(interval)
    res.json({ status: 'ok' })
  }

  function onTimeout () {
    clearInterval(interval)
    res.status(504).json({ error: 'Timed out waiting for traces to flush' })
  }

  interval = setInterval(() => {
    const stats = tracer._tracer._exporter?._writer?._stats || {}
    if (stats.count === stats.acked || Date.now() - start > timeout) {
      if (stats.count === stats.acked) {
        onFlush()
      } else {
        onTimeout()
      }
    }
  }, 50)
})

app.listen(7777, '0.0.0.0', () => {
  tracer.trace('init.service', () => {})
  console.log('listening')
})
