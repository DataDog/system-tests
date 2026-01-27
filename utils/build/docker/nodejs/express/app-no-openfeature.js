'use strict'

// Minimal app to test dd-trace works without OpenFeature installed.
// See: https://github.com/DataDog/dd-trace-js/issues/6986

const tracer = require('dd-trace').init()
const app = require('express')()

app.get('/', (req, res) => {
  res.send('Hello\n')
})

app.listen(7777, '0.0.0.0', () => {
  tracer.trace('init.service', () => {})
  console.log('listening')
})
