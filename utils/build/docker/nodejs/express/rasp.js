'use strict'

const { statSync } = require('fs')
const { execSync, execFileSync } = require('child_process')
const http = require('http')
const pg = require('pg')

function initRaspEndpoints (app) {
  const pool = new pg.Pool()

  app.get('/rasp/ssrf', (req, res) => {
    const clientRequest = http.get(`http://${req.query.domain}`, () => {
      res.end('end')
    })
    clientRequest.on('error', (e) => {
      if (e.name === 'DatadogRaspAbortError') {
        // throwing in event emitter will bubble up to the process unhandled error handler
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
        // throwing in event emitter will bubble up to the process unhandled error handler
        throw e
      }
      res.writeHead(500).end(e.message)
    })
  })

  app.get('/rasp/sqli', async (req, res) => {
    try {
      await pool.query(`SELECT * FROM users WHERE id='${req.query.user_id}'`)
    } catch (e) {
      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }

      res.writeHead(500).end(e.message)
      return
    }

    res.end('end')
  })

  app.post('/rasp/sqli', async (req, res) => {
    try {
      await pool.query(`SELECT * FROM users WHERE id='${req.body.user_id}'`)
    } catch (e) {
      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }

      res.writeHead(500).end(e.message)
      return
    }

    res.end('end')
  })

  app.get('/rasp/lfi', (req, res) => {
    let result
    try {
      result = JSON.stringify(statSync(req.query.file))
    } catch (e) {
      result = e.toString()

      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
    }
    res.send(result)
  })

  app.post('/rasp/lfi', (req, res) => {
    let result
    try {
      result = JSON.stringify(statSync(req.body.file))
    } catch (e) {
      result = e.toString()

      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
    }
    res.send(result)
  })

  app.get('/rasp/shi', (req, res) => {
    let result
    try {
      result = execSync(`ls ${req.query.list_dir}`)
    } catch (e) {
      result = e.toString()

      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
    }

    res.send(result)
  })

  app.post('/rasp/shi', (req, res) => {
    let result
    try {
      result = execSync(`ls ${req.body.list_dir}`)
    } catch (e) {
      result = e.toString()

      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
    }

    res.send(result)
  })

  app.get('/rasp/cmdi', (req, res) => {
    let result
    try {
      result = execFileSync(req.query.command)
    } catch (e) {
      result = e.toString()

      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
    }

    res.send(result)
  })

  app.post('/rasp/cmdi', (req, res) => {
    let result
    try {
      result = execFileSync(req.body.command)
    } catch (e) {
      result = e.toString()

      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
    }

    res.send(result)
  })

  app.get('/rasp/multiple', (req, res) => {
    try {
      statSync(req.query.file1)
    } catch (e) {}

    try {
      statSync(req.query.file2)
    } catch (e) {}

    try {
      statSync('../etc/passwd')
    } catch (e) {}

    res.send('OK')
  })
}

module.exports = initRaspEndpoints
