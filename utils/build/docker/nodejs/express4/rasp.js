'use strict'

const http = require('http')
function initRaspEndpoints (app) {
  app.get('/rasp/ssrf', (req, res) => {
    const cl = http.get(`http://${req.query.domain}`, () => {
      res.end('end')
    })
    cl.on('error', (e) => {
      if (e.name !== 'AbortError' && !res.headersSent) {
        res.writeHead(500).end(e.message)
        return
      }
      console.error(e)
      throw e
    })
    // TODO when blocking is supported, move this res.end to the callback
    // res.end('end')
  })

  app.post('/rasp/ssrf', (req, res) => {
    const cl = http.get(`http://${req.body.domain}`, () => {
      res.end('end')
    })
    cl.on('error', (e) => {
      res.writeHead(500).end(e.message)
    })
    // TODO when blocking is supported, move this res.end to the callback
    // res.end('end')
  })
}
module.exports = initRaspEndpoints
