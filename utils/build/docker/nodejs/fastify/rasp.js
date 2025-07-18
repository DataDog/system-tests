'use strict'

const { statSync } = require('fs')
const { execSync, execFileSync } = require('child_process')
const http = require('http')
const pg = require('pg')

function initRaspEndpoints (fastify) {
  const pool = new pg.Pool()

  fastify.get('/rasp/ssrf', (request, reply) => {
    const clientRequest = http.get(`http://${request.query.domain}`, () => {
      reply.send('end')
    })
    clientRequest.on('error', (e) => {
      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
      reply.code(500).send(e.message)
    })
  })

  fastify.post('/rasp/ssrf', (request, reply) => {
    const clientRequest = http.get(`http://${request.body.domain}`, () => {
      reply.send('end')
    })
    clientRequest.on('error', (e) => {
      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
      reply.code(500).send(e.message)
    })
  })

  fastify.get('/rasp/sqli', async (request, reply) => {
    try {
      await pool.query(`SELECT * FROM users WHERE id='${request.query.user_id}'`)
    } catch (e) {
      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }

      reply.code(500)
      return e.message
    }

    return 'end'
  })

  fastify.post('/rasp/sqli', async (request, reply) => {
    try {
      await pool.query(`SELECT * FROM users WHERE id='${request.body.user_id}'`)
    } catch (e) {
      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }

      reply.code(500)
      return e.message
    }

    return 'end'
  })

  fastify.get('/rasp/lfi', async (request, reply) => {
    let result
    try {
      result = JSON.stringify(statSync(request.query.file))
    } catch (e) {
      result = e.toString()

      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
    }
    return result
  })

  fastify.post('/rasp/lfi', async (request, reply) => {
    let result
    try {
      result = JSON.stringify(statSync(request.body.file))
    } catch (e) {
      result = e.toString()

      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
    }
    return result
  })

  fastify.get('/rasp/shi', async (request, reply) => {
    let result
    try {
      result = execSync(`ls ${request.query.list_dir}`)
    } catch (e) {
      result = e.toString()

      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
    }

    return result
  })

  fastify.post('/rasp/shi', async (request, reply) => {
    let result
    try {
      result = execSync(`ls ${request.body.list_dir}`)
    } catch (e) {
      result = e.toString()

      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
    }

    return result
  })

  fastify.get('/rasp/cmdi', async (request, reply) => {
    let result
    try {
      result = execFileSync(request.query.command)
    } catch (e) {
      result = e.toString()

      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
    }

    return result
  })

  fastify.post('/rasp/cmdi', async (request, reply) => {
    let result
    try {
      result = execFileSync(request.body.command)
    } catch (e) {
      result = e.toString()

      if (e.name === 'DatadogRaspAbortError') {
        throw e
      }
    }

    return result
  })

  fastify.get('/rasp/multiple', async (request, reply) => {
    try {
      statSync(request.query.file1)
    } catch (e) { }

    try {
      statSync(request.query.file2)
    } catch (e) { }

    try {
      statSync('../etc/passwd')
    } catch (e) { }

    return 'OK'
  })
}

module.exports = initRaspEndpoints
