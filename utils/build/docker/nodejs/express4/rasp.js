'use strict'

const http = require('http')
function initRaspEndpoints (app) {
  app.get('/rasp/ssrf', (req, res) => {
    const cl = http.get(`http://${req.query.domain}`, () => {
      res.end('end')
    })
    cl.on('error', (e) => {
      // TODO when blocking is supported, throw e when is aborted
      //  to check that we are blocking as expected
      res.writeHead(500).end(e.message)
    })
  })

  app.post('/rasp/ssrf', (req, res) => {
    const cl = http.get(`http://${req.body.domain}`, () => {
      res.end('end')
    })
    cl.on('error', (e) => {
      // TODO when blocking is supported, throw e when is aborted
      //  to check that we are blocking as expected
      res.writeHead(500).end(e.message)
    })
  })
}
module.exports = initRaspEndpoints
