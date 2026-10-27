'use strict'

const request = require('http').get('http://127.0.0.1:18080', response => {
  process.exitCode = response.statusCode >= 200 && response.statusCode < 400 ? 0 : 1
  response.resume()
})

request.setTimeout(4000, () => request.destroy(new Error('Health check timed out')))
request.on('error', () => {
  process.exitCode = 1
})
