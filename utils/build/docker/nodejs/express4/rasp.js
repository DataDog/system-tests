'use strict'

const http = require('http')
function initRaspEndpoints (app) {
  app.get('/rasp/ssrf', (req, res) => {
    const clientRequest = http.get(`http://${req.query.domain}`, () => {
      res.end('end')
    })
    clientRequest.on('error', (e) => {
      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
      res.writeHead(500).end(e.message)
    })
  })

  app.post('/rasp/ssrf', (req, res) => {
    const clientRequest = http.get(`http://${req.body.domain}`, () => {
      res.end('end')
    })
    clientRequest.on('error', (e) => {
      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
      res.writeHead(500).end(e.message)
    })
  })
}
module.exports = initRaspEndpoints
