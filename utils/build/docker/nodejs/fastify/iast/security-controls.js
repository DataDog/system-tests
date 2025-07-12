'use strict'

const { Client } = require('pg')
const { execSync } = require('child_process')
const SecurityControlUtil = require('./utils/securityControlUtil')

function execQuery (user, password) {
  const sql = 'SELECT * FROM IAST_USER WHERE USERNAME = \'' + user +
    '\' AND PASSWORD = \'' + password + '\''

  const client = new Client()
  return client.connect().then(() => {
    return client.query(sql)
  })
}

function init (app, tracer) {
  app.post('/iast/sc/s/configured', (request, reply) => {
    const sanitized = SecurityControlUtil.sanitize(request.body.param)
    try {
      execSync(sanitized)
    } catch (e) {
      // ignore
    }
    reply.send('OK')
  })

  app.post('/iast/sc/s/not-configured', (request, reply) => {
    const sanitized = SecurityControlUtil.sanitize(request.body.param)
    execQuery(sanitized, 'password').then((queryResult) => {
      reply.send('OK')
    }).catch((err) => {
      reply.send('Error: ' + err)
    })
  })

  app.post('/iast/sc/s/all', (request, reply) => {
    const sanitized = SecurityControlUtil.sanitizeForAllVulns(request.body.param)
    execQuery(sanitized, 'password').then((queryResult) => {
      reply.send('OK')
    }).catch((err) => {
      reply.send('Error: ' + err)
    })
  })

  app.post('/iast/sc/s/overloaded/secure', (request, reply) => {
    const sanitized = SecurityControlUtil.overloadedSanitize(request.body.param)
    try {
      execSync(sanitized)
    } catch (e) {
      // ignore
    }
    reply.send('OK')
  })

  app.post('/iast/sc/s/overloaded/insecure', (request, reply) => {
    const sanitized = SecurityControlUtil.overloadedSanitize(null, request.body.param)
    try {
      execSync(sanitized)
    } catch (e) {
      // ignore
    }
    reply.send('OK')
  })

  app.post('/iast/sc/iv/configured', (request, reply) => {
    if (SecurityControlUtil.validate(request.body.param)) {
      try {
        execSync(request.body.param)
      } catch (e) {
        // ignore
      }
    }
    reply.send('OK')
  })

  app.post('/iast/sc/iv/not-configured', (request, reply) => {
    if (SecurityControlUtil.validate(request.body.param)) {
      execQuery(request.body.param, 'password').then((queryResult) => {
        reply.send('OK')
      }).catch((err) => {
        reply.send('Error: ' + err)
      })
    }
  })

  app.post('/iast/sc/iv/all', (request, reply) => {
    if (SecurityControlUtil.validateForAllVulns(request.body.param)) {
      execQuery(request.body.param, 'password').then((queryResult) => {
        reply.send('OK')
      }).catch((err) => {
        reply.send('Error: ' + err)
      })
    }
  })

  app.post('/iast/sc/iv/overloaded/secure', (request, reply) => {
    const { user, password } = request.body
    if (SecurityControlUtil.overloadedValidation(null, user, password)) {
      execQuery(user, password).then((queryResult) => {
        reply.send('OK')
      }).catch((err) => {
        reply.send('Error: ' + err)
      })
    }
  })

  app.post('/iast/sc/iv/overloaded/insecure', (request, reply) => {
    const { user, password } = request.body
    if (SecurityControlUtil.overloadedValidation(user, password, null)) {
      execQuery(user, password).then((queryResult) => {
        reply.send('OK')
      }).catch((err) => {
        reply.send('Error: ' + err)
      })
    }
  })
}

module.exports = init
